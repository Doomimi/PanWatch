# Local Deployment Notes (Windows + Docker Desktop)

[English](local-deployment.md) | [简体中文](local-deployment.zh-CN.md)

These notes capture the pitfalls hit while self-hosting PanWatch on Windows + Docker Desktop 4.77, plus the configuration that ended up working. Audience: self-hosters who need to build images behind a proxy and recreate containers.

## 1. Docker Desktop resolves host.docker.internal to the wrong address

Docker Desktop 4.77 on this machine resolves `host.docker.internal` to `192.168.1.120`, while the host real NIC address is `192.168.1.44`. The result is that the build stage times out pulling base images through the proxy:

```
connecting to host.docker.internal:7897: dial tcp 192.168.1.120:7897: connectex: A connection attempt failed
```

How to diagnose: run a probe container against both addresses and see which one reaches the proxy.

```powershell
docker run --rm --add-host=host.docker.internal:host-gateway sunxiao0721/panwatch:latest python /probe.py host.docker.internal 7897
docker run --rm sunxiao0721/panwatch:latest python /probe.py 172.17.0.1 7897
```

`scripts/proxy_probe.py` is a stdlib-only TCP probe; mount it into the container and run it (the image has no wget/curl, but it has Python).

Conclusion: do not rely on `host.docker.internal`. Use the real IPv4 address from `ipconfig` for the build proxy.
## 2. Docker Desktop proxy only affects image pulls, not RUN stages

Setting the proxy in Docker Desktop settings makes `docker pull` and `FROM` metadata resolution go through it, but `RUN apt-get` does not - the buildkit container has its own environment.

Fix: declare the ARGs explicitly in the Dockerfile and pass them through, then inject with --build-arg at build time.

```dockerfile
ARG http_proxy=
ARG https_proxy=
ARG no_proxy=
```

```powershell
docker build --build-arg http_proxy=http://192.168.1.44:7897 ...
```

Dockerfile lines 57-59 already declare these three ARGs, placed before the stage 3 apt.

## 3. Recreating the container must preserve the full environment

One docker run dropped two variables, which made domestic market data sources go through the proxy and return 502, so the stock catalog fetch failed entirely:

```
WARNING [src.platform.marketdata.stock_list] CN catalog fetch failed
WARNING [src.platform.marketdata.stock_list] ETF catalog fetch failed: Server error 502 Bad Gateway
```

Required environment variables:

| Variable | Value | Purpose |
|---|---|---|
| TZ | Asia/Shanghai | Timezone, affects schedulers and K-line dates |
| PLAYWRIGHT_SKIP_BROWSER_INSTALL | 1 | Skip headless browser install, otherwise startup stalls for minutes |
| NO_PROXY | localhost,127.0.0.1,host.docker.internal | Critical: domestic market sources go direct, not through the proxy |
| DATA_DIR | /app/data | Data directory |

Losing NO_PROXY is the most insidious failure - the service starts fine and the log only shows WARNINGs, but no market data ever arrives.

Fix: scripts/deploy-0.20.1.ps1 now extracts .Config.Env from the existing container instead of hardcoding:

```powershell
 = docker inspect  --format {{range .Config.Env}}{{println .}}{{end}} | Where-Object {  -match = }
```
## 4. Upgrade flow

scripts/deploy-0.20.1.ps1 covers the full 0.19.0 to 0.20.1 upgrade in six steps: confirm current state, back up the database, build the image, record the old image ID, recreate the container, verify.

The database backup uses the SQLite backup API (not a file copy, which can capture inconsistent pages):

```bash
docker exec panwatch python -c "import sqlite3,os; src=sqlite3.connect(/app/data/panwatch.db); dst=sqlite3.connect(/app/data/panwatch.db.pre-0.20.1); src.backup(dst); dst.close(); src.close(); print(backup ok)"
```

Rollback (only if verification fails):

```powershell
docker stop panwatch; docker rm panwatch
docker tag sunxiao0721/panwatch:latest OLD_IMAGE_ID
docker run -d --name panwatch -p 8000:8000 -v panwatch_data:/app/data -e TZ=Asia/Shanghai sunxiao0721/panwatch:latest
```

## 5. PowerShell script encoding traps

PowerShell 5.1 reads a BOM-less UTF-8 .ps1 as GBK, turning every Chinese character into mojibake and producing baffling syntax errors. .ps1 files must be saved as UTF-8 with BOM, and the file may contain exactly one BOM.

Do not embed Python/JS inside PowerShell here-strings - triple quotes, single quotes and Chinese characters all get eaten. Generate files with Node/Python via [IO.File]::WriteAllText(path, [Text.Encoding]::UTF8).
