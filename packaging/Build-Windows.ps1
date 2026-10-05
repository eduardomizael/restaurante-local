param(
    [ValidateSet('all', 'x86', 'x64')][string]$Architecture = 'all',
    [string]$Version,
    [string]$Revision,
    [switch]$SkipTests
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$toolRoot = Join-Path $projectRoot '.build-tools'
$buildLock = $null
$transcribing = $false
$previousLocation = Get-Location
$environmentNames = @('PATH', 'UV_CACHE_DIR', 'UV_PYTHON_INSTALL_DIR', 'UV_PROJECT_ENVIRONMENT', 'UV_PYTHON', 'PYINSTALLER_CONFIG_DIR', 'DJANGO_SETTINGS_MODULE')
$previousEnvironment = @{}
foreach ($name in $environmentNames) { $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

function Invoke-BuildTool([string]$Executable, [string[]]$Arguments) {
    # Windows PowerShell may classify native stderr as an ErrorRecord.
    # Command success is defined by its exit code, not normal progress output.
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments
        $result = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    if ($result -ne 0) { throw "Comando falhou (código $result): $Executable $($Arguments -join ' ')" }
}

function Get-ArchiveHash([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') }) }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Get-BuildTool([string]$Name, $Definition) {
    if ($Definition.version -notmatch '^\d+\.\d+\.\d+$') { throw 'Versão de ferramenta inválida.' }
    if ($Definition.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Checksum de ferramenta inválido.' }
    $directory = Join-Path $toolRoot "$Name-$($Definition.version)"
    $archive = "$directory.zip"
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host "Baixando $Name $($Definition.version)..."
        Invoke-WebRequest -UseBasicParsing -Uri $Definition.url -OutFile "$archive.download" -TimeoutSec 180
        if ((Get-ArchiveHash "$archive.download") -ne $Definition.sha256) { throw "Checksum de $Name diferente do esperado." }
        Move-Item -LiteralPath "$archive.download" -Destination $archive -Force
    }
    if ((Get-ArchiveHash $archive) -ne $Definition.sha256) { throw "Cache de $Name inválido: remova $archive e tente novamente." }
    $ready = Join-Path $directory '.ready'
    if (-not (Test-Path -LiteralPath $ready)) {
        # Only remove this known generated tool directory inside the project.
        $resolved = [IO.Path]::GetFullPath($directory)
        if (-not $resolved.StartsWith($toolRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Pasta de ferramenta fora do projeto.' }
        if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
        [IO.Compression.ZipFile]::ExtractToDirectory($archive, $directory)
        Set-Content -LiteralPath $ready -Value $Definition.sha256 -Encoding ASCII
    }
    $found = @(Get-ChildItem -LiteralPath $directory -Filter "$Name.exe" -Recurse -File)
    if ($found.Count -ne 1) { throw "Pacote de $Name sem executável único." }
    return $found[0].FullName
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Para gerar os dois pacotes, use um computador de desenvolvimento com Windows de 64 bits.' }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Instale Git para identificar a revisão do código antes de empacotar.' }
    Set-Location -LiteralPath $projectRoot
    New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
    try { $buildLock = [IO.File]::Open((Join-Path $toolRoot 'build.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch [IO.IOException] { throw 'Outro empacotamento pode estar em execução nesta pasta. Aguarde a conclusão e tente novamente.' }
    $reportPath = Join-Path $projectRoot 'dist\build-report.json'
    if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath -Force }
    $logs = Join-Path $projectRoot 'build\logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $log = Join-Path $logs ('build-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '.log')
    Start-Transcript -Path $log | Out-Null
    $transcribing = $true
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $toolchain = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'toolchain.json') -Raw | ConvertFrom-Json
    if (-not $Version) {
        $metadata = Get-Content -LiteralPath (Join-Path $projectRoot 'pyproject.toml') -Raw
        $match = [regex]::Match($metadata, '(?m)^version\s*=\s*"([^"]+)"')
        if (-not $match.Success) { throw 'Versão ausente no pyproject.toml.' }
        $Version = $match.Groups[1].Value
    }
    if ($Version -notmatch '^\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)*$') { throw 'Versão inválida.' }
    if (-not $Revision) { $Revision = (& git rev-parse HEAD).Trim(); if ($LASTEXITCODE -ne 0) { throw 'Não foi possível identificar o commit.' } }
    if ($Revision -notmatch '^[a-f0-9]{40}$') { throw 'Informe o SHA completo da revisão.' }
    $changes = @(& git status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível consultar as alterações locais.' }
    $dirty = $changes.Count -gt 0
    if ($dirty) { Write-Host 'Há alterações locais: este pacote contém o código atual da pasta, além do commit informado.' -ForegroundColor Yellow }
    $uv = Get-BuildTool 'uv' $toolchain.uv
    $env:PATH = (Split-Path -Parent $uv) + ';' + $env:PATH
    if (-not $SkipTests) {
        $rtk = Get-BuildTool 'rtk' $toolchain.rtk
        $env:PATH = (Split-Path -Parent $rtk) + ';' + $env:PATH
    }
    $env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.uv-python'
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $toolRoot 'pyinstaller'
    [Environment]::SetEnvironmentVariable('DJANGO_SETTINGS_MODULE', $null, 'Process')
    $architectures = if ($Architecture -eq 'all') { @('x86', 'x64') } else { @($Architecture) }
    $packages = @()
    foreach ($target in $architectures) {
        Write-Host "`nEmpacotando Windows $target — versão $Version — revisão $Revision" -ForegroundColor Cyan
        $cpu = if ($target -eq 'x64') { 'x86_64' } else { 'x86' }
        $request = "cpython-$($toolchain.python)-windows-$cpu-none"
        $env:UV_PROJECT_ENVIRONMENT = Join-Path $projectRoot ".venv-build-$target"
        $env:UV_PYTHON = $request
        Invoke-BuildTool $uv @('python', 'install', '--no-bin', '--no-registry', $request)
        Invoke-BuildTool $uv @('sync', '--frozen', '--group', 'build')
        if (-not $SkipTests) {
            Invoke-BuildTool $uv @('run', '--no-sync', 'python', 'manage.py', 'check', '--settings=config.test_settings')
            Invoke-BuildTool $uv @('run', '--no-sync', 'python', 'manage.py', 'makemigrations', '--check', '--dry-run', '--settings=config.test_settings')
            Invoke-BuildTool $uv @('run', '--no-sync', 'python', 'manage.py', 'test', '--settings=config.test_settings')
        }
        Invoke-BuildTool $uv @('run', '--no-sync', 'python', 'packaging/build.py', '--version', $Version, '--revision', $Revision)
        if (-not $SkipTests) { Invoke-BuildTool $uv @('run', '--no-sync', 'python', 'packaging/smoke.py') }
        $archive = Join-Path $projectRoot "dist\RestauranteLocal-windows-$target.zip"
        $packages += @{ architecture = $target; path = $archive; sha256 = (Get-ArchiveHash $archive); validated = (-not $SkipTests) }
    }
    @{ version = $Version; revision = $Revision; working_tree_changes = $dirty;
       python = $toolchain.python; uv = $toolchain.uv.version; rtk = $(if ($SkipTests) { $null } else { $toolchain.rtk.version }); packages = $packages;
       log = $log; completed_at_utc = [DateTime]::UtcNow.ToString('o') } |
       ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Write-Host "`nConcluído. Pacotes em: $(Join-Path $projectRoot 'dist')" -ForegroundColor Green
    Write-Host "Relatório: $reportPath"
    Write-Host "Log: $log"
    Write-Host 'Este comando gera arquivos locais. Publicação ocorre pelo fluxo de PR e merge na main.'
    exit 0
} catch {
    Write-Host ('Empacotamento falhou: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
    if ($buildLock) { $buildLock.Dispose() }
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process') }
    Set-Location -LiteralPath $previousLocation.Path
}
