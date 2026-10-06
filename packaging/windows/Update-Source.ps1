param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\RestauranteLocal'),
    [string]$Repository,
    [switch]$CheckOnStart,
    [switch]$NoShortcut
)
$ErrorActionPreference = 'Stop'
$lock = $null
try {
    $InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    $lock = [IO.File]::Open((Join-Path $InstallRoot 'update.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $pointer = Join-Path $InstallRoot 'current.json'
    $sourceScript = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\runtime\source_update.py'))
    $python = $null
    if (Test-Path -LiteralPath $pointer) {
        $current = Get-Content -LiteralPath $pointer -Raw | ConvertFrom-Json
        if ($current.directory -notmatch '^versions/[a-f0-9]{64}$') { throw 'Registro de versão inválido.' }
        if ($current.PSObject.Properties.Name -contains 'mode' -and $current.mode -eq 'source') {
            $version = Join-Path $InstallRoot $current.directory
            $sourceScript = Join-Path $version 'runtime\source_update.py'
            $python = Join-Path $version '.venv\Scripts\python.exe'
        }
    }
    $arguments = @($sourceScript, '--install-root', $InstallRoot)
    if ($Repository) { $arguments += @('--repository', $Repository) }
    if ($CheckOnStart) { $arguments += '--check-on-start' }
    if (-not $python) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue) -or -not (Get-Command uv -ErrorAction SilentlyContinue)) {
            throw 'Instale Git e uv e abra um novo terminal antes de instalar por código.'
        }
        if (-not (Test-Path -LiteralPath $sourceScript)) { throw 'Execute o instalador da cópia completa do repositório.' }
        $cpu = if ([Environment]::Is64BitOperatingSystem) { 'x86_64' } else { 'x86' }
    }
    # Native stderr contains normal uv progress on Windows PowerShell 5.1.
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        if ($python) { & $python @arguments }
        else { & uv run --no-project --python "cpython-3.13-windows-$cpu-none" python @arguments }
        $result = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    if ($result -ne 0) { exit $result }
    if (-not $NoShortcut -and -not $CheckOnStart) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Restaurante Local.lnk'))
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $InstallRoot 'Launch.ps1') + '"'
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.Save()
    }
    exit 0
} catch {
    Write-Host ('Falha: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($lock) { $lock.Dispose() }
}
