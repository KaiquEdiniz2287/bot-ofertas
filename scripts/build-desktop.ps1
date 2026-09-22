$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $signingKey = Join-Path $projectRoot 'desktop\src-tauri\tauri.key'
    if (-not $env:TAURI_SIGNING_PRIVATE_KEY -and -not (Test-Path -LiteralPath $signingKey)) {
        throw 'Chave do updater ausente. Restaure desktop\src-tauri\tauri.key do backup.'
    }
    if (-not $env:TAURI_SIGNING_PRIVATE_KEY) { $env:TAURI_SIGNING_PRIVATE_KEY = $signingKey }
    if ($null -eq $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD) { $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = '' }
    uv run python -m unittest discover -s tests -v
    & "$PSScriptRoot\build-backend.ps1"
    Push-Location desktop
    try {
        npm ci
        npm test
        Push-Location src-tauri
        try { cargo test } finally { Pop-Location }
        npm run tauri build
    } finally { Pop-Location }
    Get-ChildItem 'desktop\src-tauri\target\release\bundle\nsis\*.exe' | Select-Object -ExpandProperty FullName
} finally {
    Pop-Location
}
