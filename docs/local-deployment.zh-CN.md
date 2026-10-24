# 本地部署经验（Windows + Docker Desktop）

[English](local-deployment.md) | [简体中文](local-deployment.zh-CN.md)

这份备注记录在 Windows + Docker Desktop 4.77 上自托管 PanWatch 时踩过的坑，以及最终可用的配置。适用对象：需要在代理环境下构建镜像、重建容器的自托管用户。
## 1. Docker Desktop 的 host.docker.internal 解析到了错误地址

Docker Desktop 4.77 在这台机器上把 host.docker.internal 解析成了 192.168.1.120，而主机真实网卡地址是 192.168.1.44。后果是镜像构建阶段走代理拉 base image 直接超时：

`
connecting to host.docker.internal:7897: dial tcp 192.168.1.120:7897: connectex: A connection attempt failed
`

排查方法：用探针容器分别测两个地址，确认哪个能连通代理。

`powershell
docker run --rm --add-host=host.docker.internal:host-gateway sunxiao0721/panwatch:latest python /probe.py host.docker.internal 7897
docker run --rm sunxiao0721/panwatch:latest python /probe.py 172.17.0.1 7897
`

scripts/proxy_probe.py 是纯标准库的 TCP 探针，挂进容器即可用（镜像里没有 wget/curl，但有 Python）。

结论：不要依赖 host.docker.internal，直接用 ipconfig 拿到的真实 IPv4 地址配构建代理。
## 2. Docker Desktop 代理只影响镜像拉取，不影响 RUN 阶段

在 Docker Desktop 设置里填了代理，docker pull 和 FROM 的 metadata 解析会走代理，但 RUN apt-get 不会——因为 buildkit 容器里的环境变量是独立的。

解决办法：Dockerfile 里显式声明 ARG 并透传，然后构建时用 --build-arg 注入。

`dockerfile
ARG http_proxy=
ARG https_proxy=
ARG no_proxy=
`

`powershell
docker build --build-arg http_proxy=http://192.168.1.44:7897 ...
`

Dockerfile 第 57-59 行已经加了这三个 ARG，位置在 stage 3 的 pt 之前。

## 3. 重建容器时必须保留完整环境变量

一次 docker run 漏了两个变量，导致国内行情源走代理返回 502，股票目录全部拉取失败：

`
WARNING [src.platform.marketdata.stock_list] CN catalog fetch failed
WARNING [src.platform.marketdata.stock_list] ETF catalog fetch failed: Server error '502 Bad Gateway'
`

必需的环境变量：

| 变量 | 值 | 作用 |
|---|---|---|
| TZ | Asia/Shanghai | 时区，影响调度器和 K 线日期 |
| PLAYWRIGHT_SKIP_BROWSER_INSTALL | 1 | 跳过无头浏览器安装，否则启动会卡几分钟 |
| NO_PROXY | localhost,127.0.0.1,host.docker.internal | 关键：国内行情源直连，不走代理 |
| DATA_DIR | /app/data | 数据目录 |

NO_PROXY 丢失是最隐蔽的故障——服务能正常启动、日志只有 WARNING，但所有行情数据都拉不到。

解决办法：scripts/deploy-0.20.1.ps1 现在从现有容器提取 .Config.Env 复用，不再硬编码：

`powershell
 = docker inspect  --format '{{range .Config.Env}}{{println .}}{{end}}' | Where-Object {  -match '=' }
`
## 4. 升级流程

scripts/deploy-0.20.1.ps1 覆盖 0.19.0 -> 0.20.1 的完整流程，六步：确认当前状态 -> 备份数据库 -> 构建镜像 -> 记录旧镜像 ID -> 重建容器 -> 验证。

数据库备份用 SQLite 的 backup API（不是文件拷贝，避免拷贝到不一致的页面）：

`ash
docker exec panwatch python -c "import sqlite3,os; src=sqlite3.connect('/app/data/panwatch.db'); dst=sqlite3.connect('/app/data/panwatch.db.pre-0.20.1'); src.backup(dst); dst.close(); src.close(); print('backup ok')"
`

回滚命令（仅验证失败时使用）：

`powershell
docker stop panwatch; docker rm panwatch
docker tag sunxiao0721/panwatch:latest <OLD_IMAGE_ID>
docker run -d --name panwatch -p 8000:8000 -v panwatch_data:/app/data -e TZ=Asia/Shanghai sunxiao0721/panwatch:latest
`

## 5. PowerShell 脚本的编码陷阱

PowerShell 5.1 读无 BOM 的 UTF-8 .ps1 会按 GBK 解码，中文全部变乱码，报一批莫名其妙的语法错误。.ps1 必须存成 UTF-8 with BOM，且整个文件只能有一个 BOM。

写脚本时不要把 Python/JS 代码嵌进 PowerShell here-string——"""、单引号和中文都会被吃掉。用 Node/Python 生成文件，走 [IO.File]::WriteAllText(path, [Text.Encoding]::UTF8)。
