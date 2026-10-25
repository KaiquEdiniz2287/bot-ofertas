$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    uv sync --dev --frozen
    if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar as dependências Python (código $LASTEXITCODE)." }
    uv run pyinstaller --noconfirm --clean packaging/backend.spec
    if ($LASTEXITCODE -ne 0) { throw "Falha ao empacotar o backend Python (código $LASTEXITCODE)." }
    & .\dist\bot-ofertas-backend.exe check
    if ($LASTEXITCODE -ne 0) { throw 'Smoke test do backend falhou.' }
} finally {
    Pop-Location
}
