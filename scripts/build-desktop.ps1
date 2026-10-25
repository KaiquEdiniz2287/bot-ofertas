$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $releaseBuild = $env:BOT_OFERTAS_RELEASE -eq '1'
    if ($releaseBuild) {
        $signingKey = Join-Path $projectRoot 'desktop\src-tauri\tauri.key'
        if (-not $env:TAURI_SIGNING_PRIVATE_KEY -and -not (Test-Path -LiteralPath $signingKey)) {
            throw 'Chave do updater ausente. Restaure desktop\src-tauri\tauri.key do backup.'
        }
        if (-not $env:TAURI_SIGNING_PRIVATE_KEY) { $env:TAURI_SIGNING_PRIVATE_KEY = $signingKey }
    }
    uv run python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Os testes Python falharam (código $LASTEXITCODE)." }
    & "$PSScriptRoot\build-whatsapp.ps1"
    & "$PSScriptRoot\build-backend.ps1"
    Push-Location desktop
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências do desktop (código $LASTEXITCODE)." }
        npm test
        if ($LASTEXITCODE -ne 0) { throw "Os testes da interface falharam (código $LASTEXITCODE)." }
        Push-Location src-tauri
        try {
            cargo test --locked
            if ($LASTEXITCODE -ne 0) { throw "Os testes Rust falharam (código $LASTEXITCODE). O build foi interrompido nesta etapa." }
        } finally { Pop-Location }
        if ($releaseBuild) {
            npm run tauri -- build -- --locked
        } else {
            & '.\node_modules\.bin\tauri.cmd' build --config 'src-tauri\tauri.installer.conf.json' -- --locked
        }
        if ($LASTEXITCODE -ne 0) { throw "A geração do instalador falhou (código $LASTEXITCODE)." }
    } finally { Pop-Location }
    Get-ChildItem 'desktop\src-tauri\target\release\bundle\nsis\*.exe' | Select-Object -ExpandProperty FullName
} finally {
    Pop-Location
}
