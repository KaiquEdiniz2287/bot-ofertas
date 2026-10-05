$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

# O Tauri copia os executáveis de dist para target/debug. Uma ponte órfã de
# uma execução anterior bloqueia essa cópia no Windows (os error 32).
$debugBridge = Join-Path $projectRoot 'desktop\src-tauri\target\debug\bot-ofertas-whatsapp.exe'
if (Test-Path -LiteralPath $debugBridge) {
    $debugBridgePath = (Resolve-Path -LiteralPath $debugBridge).Path
    foreach ($process in @(Get-CimInstance Win32_Process -Filter "Name = 'bot-ofertas-whatsapp.exe'")) {
        $processPath = $process.ExecutablePath -replace '^\\\\\?\\', ''
        if (-not [string]::Equals($processPath, $debugBridgePath, [StringComparison]::OrdinalIgnoreCase)) { continue }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.ParentProcessId)"
        if ($parent) {
            throw "O componente WhatsApp de desenvolvimento ainda está em uso (PID $($process.ProcessId)). Encerre a instância anterior do aplicativo antes de iniciar outra."
        }
        Write-Host "Encerrando componente WhatsApp órfão da execução anterior (PID $($process.ProcessId))..."
        Stop-Process -Id $process.ProcessId -ErrorAction Stop
        Wait-Process -Id $process.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
}

function Test-NeedsBuild($target, $sources) {
    if (-not (Test-Path -LiteralPath $target)) { return $true }
    $builtAt = (Get-Item -LiteralPath $target).LastWriteTimeUtc
    foreach ($source in $sources) {
        if ($source.LastWriteTimeUtc -gt $builtAt) { return $true }
    }
    return $false
}

$backend = Join-Path $projectRoot 'dist\bot-ofertas-backend.exe'
$backendSources = @(
    Get-ChildItem -LiteralPath (Join-Path $projectRoot 'ofertas') -Filter '*.py' -Recurse -File
    Get-Item -LiteralPath (Join-Path $projectRoot 'pyproject.toml'), (Join-Path $projectRoot 'uv.lock'), (Join-Path $projectRoot 'packaging\backend.spec')
)
if (Test-NeedsBuild $backend $backendSources) {
    Write-Host 'Atualizando backend Python para o modo de desenvolvimento...'
    & (Join-Path $PSScriptRoot 'build-backend.ps1')
    if (Test-NeedsBuild $backend $backendSources) { throw 'O backend empacotado continua desatualizado.' }
}

$whatsapp = Join-Path $projectRoot 'dist\bot-ofertas-whatsapp.exe'
$whatsappSources = @(
    Get-ChildItem -LiteralPath (Join-Path $projectRoot 'whatsapp-bridge') -Filter '*.cjs' -Recurse -File
    Get-Item -LiteralPath (Join-Path $projectRoot 'whatsapp-bridge\package.json')
)
if (Test-NeedsBuild $whatsapp $whatsappSources) {
    Write-Host 'Atualizando componente WhatsApp para o modo de desenvolvimento...'
    & (Join-Path $PSScriptRoot 'build-whatsapp.ps1')
    if (Test-NeedsBuild $whatsapp $whatsappSources) { throw 'O componente WhatsApp empacotado continua desatualizado.' }
}
