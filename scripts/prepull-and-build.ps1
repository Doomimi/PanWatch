# Pull base images through the host proxy, then build with the proxy injected.
# Run this in your own terminal. Requires the Docker Desktop proxy to point at
# host.docker.internal:7897 (Settings > Resources > Proxies).

$ErrorActionPreference = "Stop"
$Proxy = "http://host.docker.internal:7897"
$ProjectRoot = "D:\tools\CodeX\PanWatch"

Write-Host "=== Pre-pull base images through the Docker Desktop proxy ==="
docker pull python:3.11-slim-bookworm
docker pull node:24.14.0-alpine
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Pre-pull failed. The Docker Desktop proxy is not working for the build network."
    Write-Host "Check: Settings > Resources > Proxies > Manual proxy configuration"
    Write-Host "  HTTP Proxy:  http://host.docker.internal:7897"
    Write-Host "  HTTPS Proxy: http://host.docker.internal:7897"
    Write-Host "  Bypass:     localhost,127.0.0.1,host.docker.internal"
    Write-Host "Then Apply & restart, and run this again."
    exit 1
}

Write-Host "`n=== Build (base images now cached, apt still needs the proxy) ==="
Set-Location $ProjectRoot
$env:HTTP_PROXY = $Proxy
$env:HTTPS_PROXY = $Proxy
$env:http_proxy = $Proxy
$env:https_proxy = $Proxy
$env:NO_PROXY = "localhost,127.0.0.1,host.docker.internal"
docker build --platform linux/amd64 --build-arg VERSION=0.20.1 -t sunxiao0721/panwatch:0.20.1 .
if ($LASTEXITCODE -ne 0) { Write-Host "Build failed. Container untouched."; exit 1 }

Write-Host "`n=== Build succeeded ==="
docker images sunxiao0721/panwatch --format "{{.Repository}}:{{.Tag}} {{.ID}}"
Write-Host "Now run .\scripts\deploy-0.20.1.ps1 and choose to skip the build step,"
Write-Host "or recreate the container manually with the new image."
