$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
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
