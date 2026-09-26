$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$bridgeRoot = Join-Path $projectRoot 'whatsapp-bridge'
Push-Location $bridgeRoot
try {
    npm ci
    npm test
    npm run build
    & (Join-Path $projectRoot 'dist\bot-ofertas-whatsapp.exe') --self-test
} finally {
    Pop-Location
}
