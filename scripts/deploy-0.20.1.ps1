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
docker exec $Container ls -la /app/data/*.db*

Write-Host "`n=== Step 2: build the image (5-10 min) ==="
Set-Location $ProjectRoot
& (Join-Path $ProjectRoot "scripts\build.ps1") -Version $Version
if ($LASTEXITCODE -ne 0) { Write-Host "Build failed. Do not continue."; exit 1 }

Write-Host "`n=== Step 3: record the old image id for rollback ==="
docker images $ImageName --format "{{.Repository}}:{{.Tag}} {{.ID}}"

Write-Host "`n=== Step 4: recreate the container ==="
Write-Host "NOTE: adjust the run flags below to match your original container."
docker inspect $Container --format "{{json .Config.Env}}" | Write-Host
docker inspect $Container --format "Ports: {{json .HostConfig.PortBindings}}" | Write-Host
docker inspect $Container --format "Mounts: {{json .Mounts}}" | Write-Host
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
