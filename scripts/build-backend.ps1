$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    uv sync --dev --frozen
    uv run pyinstaller --noconfirm --clean packaging/backend.spec
    & .\dist\bot-ofertas-backend.exe check
    if ($LASTEXITCODE -ne 0) { throw 'Smoke test do backend falhou.' }
} finally {
    Pop-Location
}
