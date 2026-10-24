# PanWatch 0.19.0 -> 0.20.1 部署脚本（手动执行）
# 用户在自己的终端里面一来一来执行，每步都要看输出。

$ErrorActionPreference = "Stop"
$Version = "0.20.1"
$ImageName = "sunxiao0721/panwatch"
$Container = "panwatch"

Write-Host "=== 第 0 步: 确认当前状态 ==="
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
docker exec $Container cat /app/VERSION
$answer = Read-Host "当前容器 VERSION 应该是 0.19.0，确认继续? (yes/no)"
if ($answer -ne "yes") { Write-Host "已取消"; exit }

Write-Host "`n=== 第 1 步: 备份数据库（关键，不要跳过） ==="
docker exec $Container python -c "import sqlite3,os; p=os.environ.get('DATA_DIR','/app/data')+'/panwatch.db'; print('db:', p, os.path.getsize(p), 'bytes')"
docker exec $Container python -c "import sqlite3,os; src=sqlite3.connect(os.environ.get('DATA_DIR','/app/data')+'/panwatch.db'); dst=sqlite3.connect(os.environ.get('DATA_DIR','/app/data')+'/panwatch.db.pre-0.20.1'); src.backup(dst); dst.close(); src.close(); print('backup ok')"
docker exec $Container ls -la /app/data/*.db*

Write-Host "`n=== 第 2 步: 构建新镜像 ==="
Write-Host "此步需要 5-10 分钟（前端 pnpm build + Docker 多阶段构建）"
Set-Location "D:\tools\CodeX\PanWatch"
& .\scripts\build.ps1 -Version $Version
if ($LASTEXITCODE -ne 0) { Write-Host "构建失败，不要继续"; exit 1 }

Write-Host "`n=== 第 3 步: 记录旧镜像 ID（回滚用） ==="
docker images $ImageName --format "{{.Repository}}:{{.Tag}} {{.ID}}"

Write-Host "`n=== 第 4 步: 重建容器 ==="
docker stop $Container
docker rm $Container
# 注意: 按你原来的 run 参数调整；数据卷 panwatch_data 保按原样挂载
docker run -d --name $Container -p 8000:8000 -v panwatch_data:/app/data -e TZ=Asia/Shanghai ${ImageName}:$Version

Write-Host "`n=== 第 5 步: 验证 ==="
Start-Sleep -Seconds 15
docker ps --filter "name=$Container" --format "table {{.Names}}\t{{.Status}}"
docker exec $Container cat /app/VERSION
docker logs --tail 30 $Container

Write-Host "`n=== 验证清单 ==="
Write-Host "1. 容器 Status 应为 healthy（可能需要等 30-60 秒）"
Write-Host "2. /app/VERSION 应为 0.20.1"
Write-Host "3. 日志无异常崩溃堆栈"
Write-Host "4. 浏览器打开 http://localhost:8000 能正常登录"
Write-Host "5. 手动触发一次价格提醒，确认推送时延降低"
Write-Host "6. 跑一次深度分析，在详情页看“决策溯源”面板是否显示 state.final_rating"

Write-Host "`n=== 回滚命令（仅当验证失败时使用） ==="
Write-Host "docker stop $Container; docker rm $Container"
Write-Host "docker tag ${ImageName}:latest <OLD_IMAGE_ID>"
Write-Host "docker run -d --name $Container -p 8000:8000 -v panwatch_data:/app/data -e TZ=Asia/Shanghai ${ImageName}:latest"
