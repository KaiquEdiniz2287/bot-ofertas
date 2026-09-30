$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$bridgeRoot = Join-Path $projectRoot 'whatsapp-bridge'
Push-Location $bridgeRoot
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências do WhatsApp." }
    npm test
    if ($LASTEXITCODE -ne 0) { throw "Os testes do WhatsApp falharam." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o componente do WhatsApp." }
    & (Join-Path $projectRoot 'dist\bot-ofertas-whatsapp.exe') --self-test
    if ($LASTEXITCODE -ne 0) { throw "O executável do WhatsApp falhou no autoteste." }
} finally {
    Pop-Location
}
