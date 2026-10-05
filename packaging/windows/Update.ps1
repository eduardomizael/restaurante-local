param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\RestauranteLocal'),
    [string]$PackageDirectory,
    [string]$PackagePath,
    [string]$ExpectedHash,
    [string]$ManifestUrl = 'https://eduardomizael.github.io/restaurante-local/latest.json',
    [switch]$CheckOnStart,
    [switch]$NoShortcut
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$lock = $null
$work = $null
$versionDirectory = $null
$copiedVersion = $false
$activated = $false

function Get-PackageHash([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') }) }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Expand-VerifiedPackage([string]$Archive, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $destinationPrefix = [IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
        [long]$totalSize = 0
        foreach ($entry in $zip.Entries) {
            $target = [IO.Path]::GetFullPath((Join-Path $Destination $entry.FullName))
            if (-not $target.StartsWith($destinationPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'O pacote contém um caminho fora da pasta de instalação.'
            }
            $totalSize += $entry.Length
            if ($totalSize -gt 1GB) { throw 'Pacote excede o limite de tamanho.' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($Archive, $Destination)
}

try {
    Write-Host 'Feche o Restaurante Local pela opção Sair na bandeja antes de continuar.'
    $InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    # All installers/updaters share this lock, even when started from another folder.
    $lock = [IO.File]::Open((Join-Path $InstallRoot 'update.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $urlFile = Join-Path $InstallRoot 'update-url.txt'
    if (Test-Path -LiteralPath $urlFile) { $ManifestUrl = (Get-Content -LiteralPath $urlFile -Raw).Trim() }
    $currentPath = Join-Path $InstallRoot 'current.json'
    if (Test-Path -LiteralPath $currentPath) {
        $current = Get-Content -LiteralPath $currentPath -Raw | ConvertFrom-Json
        if ($current.directory -notmatch '^versions/[a-f0-9]{64}$') { throw 'Registro de versão inválido.' }
        $preflight = Join-Path (Join-Path $InstallRoot $current.directory) 'Manutencao.exe'
        $check = Start-Process -FilePath $preflight -ArgumentList @('check_update_allowed') -NoNewWindow -Wait -PassThru
        if ($check.ExitCode -eq 2 -and $CheckOnStart) { exit 0 }
        if ($check.ExitCode -ne 0) { throw 'Não é possível atualizar agora. Feche o aplicativo e confira os dados locais.' }
    }
    $work = Join-Path $InstallRoot ('staging-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work | Out-Null
    $expectedVersion = $null
    $expectedRevision = $null
    if ($PackageDirectory) {
        $source = [IO.Path]::GetFullPath($PackageDirectory)
        $payload = Join-Path $source 'app'
        if (-not (Test-Path -LiteralPath (Join-Path $payload 'Manutencao.exe'))) { throw 'Pacote incompleto.' }
        $buildInfo = Get-Content -LiteralPath (Join-Path $payload 'version.json') -Raw | ConvertFrom-Json
        $version = $buildInfo.version
        $revision = $buildInfo.revision
        # Offline installer identity includes every payload file, not just its version label.
        $hashInput = (Get-ChildItem -LiteralPath $payload -File -Recurse | Sort-Object FullName | ForEach-Object {
            $_.FullName.Substring($payload.Length) + ':' + (Get-PackageHash $_.FullName)
        }) -join "`n"
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $digest = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($hashInput)) | ForEach-Object { $_.ToString('x2') }) }
        finally { $sha.Dispose() }
    } else {
        $archive = Join-Path $work 'release.zip'
        if ($PackagePath) {
            if ($ExpectedHash -notmatch '^[a-fA-F0-9]{64}$') { throw 'Informe ExpectedHash para um pacote local.' }
            Copy-Item -LiteralPath $PackagePath -Destination $archive
        } else {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $manifestUri = [Uri]$ManifestUrl
            if ($manifestUri.Scheme -ne 'https' -and -not $manifestUri.IsLoopback) { throw 'O servidor de atualização precisa usar HTTPS.' }
            $manifest = Invoke-RestMethod -Uri ($ManifestUrl + '?t=' + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) -TimeoutSec 8 -Headers @{ 'Cache-Control' = 'no-cache' }
            $expectedVersion = $manifest.version
            $expectedRevision = $manifest.revision
            if ($expectedRevision -notmatch '^[a-f0-9]{40}$') { throw 'Revisão inválida no manifesto.' }
            if (Test-Path -LiteralPath $currentPath) {
                $current = Get-Content -LiteralPath $currentPath -Raw | ConvertFrom-Json
                if ($current.revision -eq $expectedRevision -and -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'update-failed.txt'))) {
                    Write-Host "A revisão $expectedRevision já está instalada."
                    exit 0
                }
            }
            if ($manifest.package -notmatch '^RestauranteLocal-[a-f0-9]{64}\.zip$') { throw 'Nome de pacote inválido.' }
            $ExpectedHash = $manifest.sha256
            $packageUri = [Uri]::new($manifestUri, [string]$manifest.package)
            Write-Host "Baixando versão $expectedVersion da main..."
            Invoke-WebRequest -UseBasicParsing -Uri $packageUri -OutFile $archive -TimeoutSec 120
        }
        if ($ExpectedHash -notmatch '^[a-fA-F0-9]{64}$') { throw 'Checksum inválido.' }
        $digest = Get-PackageHash $archive
        if ($digest -ne $ExpectedHash.ToLowerInvariant()) { throw 'Checksum diferente: atualização cancelada.' }
        $source = Join-Path $work 'extracted'
        Expand-VerifiedPackage $archive $source
        $payload = Join-Path $source 'app'
        $buildInfo = Get-Content -LiteralPath (Join-Path $payload 'version.json') -Raw | ConvertFrom-Json
        $version = $buildInfo.version
        $revision = $buildInfo.revision
    }
    if ($version -notmatch '^\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)*$') { throw 'Versão inválida.' }
    if ($expectedVersion -and $version -ne $expectedVersion) { throw 'Versão do pacote difere da release.' }
    if ($revision -notmatch '^[a-f0-9]{40}$') { throw 'Revisão inválida no pacote.' }
    if ($expectedRevision -and $revision -ne $expectedRevision) { throw 'Revisão do pacote difere do manifesto.' }
    foreach ($required in @('RestauranteLocal.exe', 'Manutencao.exe', '_internal')) {
        if (-not (Test-Path -LiteralPath (Join-Path $payload $required))) { throw "Pacote sem $required." }
    }
    foreach ($required in @('Launch.ps1', 'Iniciar.bat', 'Atualizar.bat', 'Update.ps1')) {
        if (-not (Test-Path -LiteralPath (Join-Path $source $required))) { throw "Pacote sem $required." }
    }
    $versionDirectory = Join-Path $InstallRoot ('versions\' + $digest)
    $reuseVersion = $false
    if (Test-Path -LiteralPath $versionDirectory) {
        if ((Test-Path -LiteralPath $currentPath) -and $current.directory -eq ('versions/' + $digest)) {
            if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'update-failed.txt'))) {
                Write-Host 'Este pacote já está instalado.'
                exit 0
            }
            $reuseVersion = $true
        } else {
            throw 'Este pacote já está presente, mas não pode ser ativado. Confira a versão incompleta com suporte técnico.'
        }
    }
    New-Item -ItemType Directory -Path (Join-Path $InstallRoot 'versions') -Force | Out-Null
    if (-not $reuseVersion) {
        Copy-Item -LiteralPath $payload -Destination $versionDirectory -Recurse
        $copiedVersion = $true
    }
    # Shared custom settings stay outside version folders and survive every upgrade.
    $settingsPath = Join-Path $InstallRoot '.env'
    if (Test-Path -LiteralPath $settingsPath) { Copy-Item -LiteralPath $settingsPath -Destination (Join-Path $versionDirectory '.env') }
    Write-Host 'Preparando os dados com backup automático...'
    Set-Content -LiteralPath (Join-Path $InstallRoot 'update-failed.txt') -Value 'Atualização de dados interrompida. Execute Atualizar.bat e confira o backup.' -Encoding UTF8
    $maintenance = Join-Path $versionDirectory 'Manutencao.exe'
    $process = Start-Process -FilePath $maintenance -ArgumentList @('initialize_local') -WorkingDirectory $versionDirectory -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        Set-Content -LiteralPath (Join-Path $InstallRoot 'update-failed.txt') -Value 'Preparação dos dados falhou. Execute Atualizar.bat e confira o backup.' -Encoding UTF8
        throw 'Preparação falhou. A versão ativa não foi trocada. Confira as mensagens e o backup antes de tentar novamente.'
    }
    foreach ($file in @('Launch.ps1', 'Iniciar.bat', 'Atualizar.bat', 'Update.ps1')) {
        $original = Join-Path $source $file
        $destination = Join-Path $InstallRoot $file
        if ([IO.Path]::GetFullPath($original) -ne [IO.Path]::GetFullPath($destination)) {
            Copy-Item -LiteralPath $original -Destination $destination -Force
        }
    }
    $pointer = Join-Path $InstallRoot 'current.json'
    $temporary = Join-Path $InstallRoot 'current.tmp'
    @{ version = $version; revision = $revision; directory = 'versions/' + $digest } | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding UTF8
    if (Test-Path -LiteralPath $pointer) { [IO.File]::Replace($temporary, $pointer, (Join-Path $InstallRoot 'previous.json'), $true) }
    else { [IO.File]::Move($temporary, $pointer) }
    $activated = $true
    $failureMarker = Join-Path $InstallRoot 'update-failed.txt'
    if (Test-Path -LiteralPath $failureMarker) { Remove-Item -LiteralPath $failureMarker -Force }
    if (-not $NoShortcut -and -not $CheckOnStart) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Restaurante Local.lnk'))
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $InstallRoot 'Launch.ps1') + '"'
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.IconLocation = (Join-Path $versionDirectory 'RestauranteLocal.exe') + ',0'
        $shortcut.Save()
    }
    Write-Host "Versão $version instalada. Abra Restaurante Local pelo atalho."
    Write-Host "Para próximas atualizações, execute: $(Join-Path $InstallRoot 'Atualizar.bat')"
    exit 0
} catch {
    Write-Host ('Falha: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($lock) { $lock.Dispose() }
    if ($copiedVersion -and -not $activated -and $versionDirectory) {
        $resolvedVersion = [IO.Path]::GetFullPath($versionDirectory)
        $versionPrefix = $InstallRoot.TrimEnd('\') + '\versions\'
        if ($resolvedVersion.StartsWith($versionPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedVersion -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    # Resolve and constrain the exact staging path before recursive removal.
    if ($work -and (Test-Path -LiteralPath $work)) {
        $resolvedWork = [IO.Path]::GetFullPath($work)
        $prefix = $InstallRoot.TrimEnd('\') + '\staging-'
        if ($resolvedWork.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedWork -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
