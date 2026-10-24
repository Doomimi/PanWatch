# PanWatch 0.19.0 -> 0.20.1 upgrade script
# Run step by step in your own terminal and read the output of each step.

$ErrorActionPreference = "Stop"
$Version = "0.20.1"
$ImageName = "sunxiao0721/panwatch"
$Container = "panwatch"
$ProjectRoot = "D:\tools\CodeX\PanWatch"

Write-Host "=== Step 0: confirm current state ==="
docker ps -a --format "table {{.Names}}	{{.Image}}	{{.Status}}"
docker exec $Container cat /app/VERSION
$answer = Read-Host "Container VERSION should be 0.19.0. Continue? (yes/no)"
if ($answer -ne "yes") { Write-Host "Aborted."; exit 0 }

Write-Host "`n=== Step 1: back up the database (do not skip) ==="
docker exec $Container python -c "import os; p=os.environ.get('DATA_DIR','/app/data')+'/panwatch.db'; print('db:', p, os.path.getsize(p), 'bytes')"
docker exec $Container python -c "import sqlite3, os; d=os.environ.get('DATA_DIR','/app/data'); s=sqlite3.connect(d+'/panwatch.db'); t=sqlite3.connect(d+'/panwatch.db.pre-0.20.1'); s.backup(t); t.close(); s.close(); print('backup ok')"
docker exec $Container ls -la /app/data/ | Select-String "panwatch.db"

Write-Host "`n=== Step 2: build the image ==="
Write-Host "NOTE: skipping scripts/build.ps1. It calls a host pnpm that is missing here,"
Write-Host "      but the Dockerfile builds the frontend inside node:24.14.0-alpine with a"
Write-Host "      corepack-pinned pnpm, so the host pnpm is not needed at all."
Write-Host "The build needs the host proxy. Docker Desktop 4.77 resolves"
Write-Host "host.docker.internal to the wrong LAN address here, so the script probes the"
Write-Host "real host IP and pins the proxy to it."
Set-Location $ProjectRoot
$hostIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" -and $_.IPAddress -ne "192.168.1.120" } | Select-Object -First 1).IPAddress
if (-not $hostIp) { $hostIp = Read-Host "Enter your Windows host LAN IP (e.g. 192.168.1.44)" }
$proxy = "http://${hostIp}:7897"
Write-Host "Using build proxy: $proxy"
$env:HTTP_PROXY = $proxy
$env:HTTPS_PROXY = $proxy
$env:http_proxy = $proxy
$env:https_proxy = $proxy
$env:NO_PROXY = "localhost,127.0.0.1"
# RUN 阶段的 apt 不跟 Docker Desktop 代理，必须作为 build-arg 显式传入（Dockerfile 已声明 ARG）。
docker build --platform linux/amd64 --build-arg VERSION=$Version --build-arg http_proxy=$proxy --build-arg https_proxy=$proxy --build-arg no_proxy=localhost,127.0.0.1 -t ${ImageName}:$Version .
if ($LASTEXITCODE -ne 0) { Write-Host "Build failed. Do not continue."; exit 1 }

Write-Host "`n=== Step 3: record the old image id for rollback ==="
docker images $ImageName --format "{{.Repository}}:{{.Tag}} {{.ID}}"
Write-Host "Current container image id (save this for rollback):"
docker inspect $Container --format "{{.Image}}"

Write-Host "`n=== Step 4: recreate the container ==="
Write-Host "Your current container config:"
docker inspect $Container --format "Env: {{json .Config.Env}}"
docker inspect $Container --format "Ports: {{json .HostConfig.PortBindings}}"
docker inspect $Container --format "Mounts: {{json .Mounts}}"
Write-Host "Compare with the docker run flags below. Adjust them if anything differs."
$confirm = Read-Host "Recreate the container now? (yes/no)"
if ($confirm -ne "yes") { Write-Host "Stopped before recreate. Image is built, container untouched."; exit 0 }
docker stop $Container
docker rm $Container
docker run -d --name $Container -p 8000:8000 -v panwatch_data:/app/data -e TZ=Asia/Shanghai ${ImageName}:$Version

Write-Host "`n=== Step 5: verify ==="
Start-Sleep -Seconds 20
docker ps --filter "name=$Container" --format "table {{.Names}}	{{.Status}}"
docker exec $Container cat /app/VERSION
docker logs --tail 40 $Container

Write-Host "`n=== Verification checklist ==="
Write-Host "1. Status should become healthy (may need 30-60s)"
Write-Host "2. /app/VERSION should be 0.20.1"
Write-Host "3. No crash stack traces in the log"
Write-Host "4. http://localhost:8000 loads and login works"
Write-Host "5. Trigger a price alert manually and confirm lower latency"
Write-Host "6. Run a deep analysis and check the Decision provenance panel shows state.final_rating"

Write-Host "`n=== Rollback (only if verification fails) ==="
Write-Host "docker stop $Container; docker rm $Container"
Write-Host "docker tag ${ImageName}:latest OLD_IMAGE_ID_FROM_STEP_3"
Write-Host "docker run -d --name $Container -p 8000:8000 -v panwatch_data:/app/data -e TZ=Asia/Shanghai ${ImageName}:latest"
