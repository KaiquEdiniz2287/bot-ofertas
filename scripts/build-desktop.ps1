$ErrorActionPreference = 'Stop'
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
    & "$PSScriptRoot\build-whatsapp.ps1"
    & "$PSScriptRoot\build-backend.ps1"
    Push-Location desktop
    try {
        npm ci
        npm test
        Push-Location src-tauri
        try { cargo test } finally { Pop-Location }
        if ($releaseBuild) {
            npm run tauri build
        } else {
            & '.\node_modules\.bin\tauri.cmd' build --config 'src-tauri\tauri.installer.conf.json'
        }
    } finally { Pop-Location }
    Get-ChildItem 'desktop\src-tauri\target\release\bundle\nsis\*.exe' | Select-Object -ExpandProperty FullName
} finally {
    Pop-Location
}
