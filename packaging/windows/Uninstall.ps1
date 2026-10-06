param(
    [string]$InstallRoot,
    [string]$DataRoot,
    [string]$ShortcutPath,
    [switch]$DeleteData,
    [switch]$Yes
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$defaultInstall = Join-Path $env:LOCALAPPDATA 'Programs\RestauranteLocal'
if (-not $InstallRoot) {
    $InstallRoot = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'current.json')) { $PSScriptRoot } else { $defaultInstall }
}
$updateLock = $null
$mutexes = @()
$problems = [Collections.Generic.List[string]]::new()
$origins = @()
$dataLocations = @()
$createdLock = $false
$removalStarted = $false

function Normalize-Directory([string]$Path) {
    if (-not [IO.Path]::IsPathRooted($Path)) { throw "Informe um caminho absoluto: $Path" }
    $full = [IO.Path]::GetFullPath($Path)
    # Existing Windows paths may use 8.3 aliases such as RUNNER~1.
    # Compare ownership using the filesystem's full name in both cases.
    if (Test-Path -LiteralPath $full) { $full = (Get-Item -LiteralPath $full -Force).FullName }
    return $full.TrimEnd('\', '/')
}

function Assert-SafeDirectory([string]$Path, [switch]$ManagedSource) {
    $full = Normalize-Directory $Path
    $root = [IO.Path]::GetPathRoot($full).TrimEnd('\', '/')
    if ($full -eq $root) { throw "Não é permitido remover a raiz do disco: $full" }
    $protected = @($env:SystemRoot, $env:USERPROFILE, $env:LOCALAPPDATA, $env:APPDATA,
                   $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData, $env:TEMP,
                   [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('MyDocuments'))
    foreach ($directory in $protected) {
        if (-not $directory) { continue }
        $candidate = Normalize-Directory $directory
        if ($candidate -eq $full -or $candidate.StartsWith($full + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "Pasta protegida ou que contém uma pasta protegida: $full"
        }
    }
    if (-not $ManagedSource -and (Test-Path -LiteralPath (Join-Path $full '.git'))) { throw "Não remover uma pasta de desenvolvimento: $full" }
    # Resolve the whole ancestry before any recursive removal. Junction targets
    # are never accepted as installation/data roots.
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Pasta com link/junção não pode ser usada como raiz: $cursor" }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        $cursor = if ($parent) { $parent.FullName } else { $null }
    }
    return $full
}

function Get-MutexName([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Path.ToLowerInvariant())) | ForEach-Object { $_.ToString('x2') })
        return "Local\RestauranteLocal-$digest"
    } finally { $sha.Dispose() }
}

function Add-DataLocation($Location) {
    $path = Assert-SafeDirectory ([string]$Location.data_root)
    if ($Location.mutex_name -notmatch '^Local\\RestauranteLocal-[a-f0-9]{64}$') { throw 'Identificação de dados inválida.' }
    if (-not @($script:dataLocations | Where-Object { $_.data_root -eq $path }).Count) {
        $script:dataLocations += @{ data_root = $path; mutex_name = [string]$Location.mutex_name }
    }
}

function Remove-OwnedTree([string]$Path, [string[]]$Skip = @()) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    if ($Skip -contains $Path) { return }
    try {
        $item = Get-Item -LiteralPath $Path -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            # Delete the link itself, never enumerate or follow its target.
            if ($item.PSIsContainer) { [IO.Directory]::Delete($Path) }
            else { [IO.File]::Delete($Path) }
        } elseif ($item.PSIsContainer) {
            foreach ($child in @(Get-ChildItem -LiteralPath $Path -Force)) { Remove-OwnedTree $child.FullName $Skip }
            if (-not @(Get-ChildItem -LiteralPath $Path -Force).Count) { [IO.Directory]::Delete($Path) }
        } else { Remove-Item -LiteralPath $Path -Force }
    } catch { $script:problems.Add("$Path — $($_.Exception.Message)") }
}

function Get-RemainingPaths([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $Path
    try {
        $item = Get-Item -LiteralPath $Path -Force
        if ($item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            foreach ($child in @(Get-ChildItem -LiteralPath $Path -Force)) { Get-RemainingPaths $child.FullName }
        }
    } catch { $script:problems.Add("$Path — não foi possível listar: $($_.Exception.Message)") }
}

try {
    $InstallRoot = Assert-SafeDirectory $InstallRoot
    $infoPath = Join-Path $InstallRoot 'uninstall-info.json'
    $lockPath = Join-Path $InstallRoot 'update.lock'
    $currentPath = Join-Path $InstallRoot 'current.json'
    foreach ($control in @($infoPath, $lockPath, $currentPath)) {
        if ((Test-Path -LiteralPath $control) -and ((Get-Item -LiteralPath $control -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Arquivo de controle com link: $control. Nada foi removido." }
    }
    $identified = $InstallRoot -eq (Normalize-Directory $defaultInstall)
    if (Test-Path -LiteralPath $infoPath) {
        $info = Get-Content -LiteralPath $infoPath -Raw | ConvertFrom-Json
        if ($info.application -ne 'RestauranteLocal' -or $info.schema_version -ne 1 -or
            (Normalize-Directory $info.install_root) -ne $InstallRoot) { throw 'Registro de desinstalação não corresponde a esta pasta.' }
        $identified = $true
        foreach ($location in $info.data_locations) { Add-DataLocation $location }
        $origins = @($info.origins)
    }
    if (Test-Path -LiteralPath $currentPath) {
        $current = Get-Content -LiteralPath $currentPath -Raw | ConvertFrom-Json
        if ($current.directory -notmatch '^versions/[a-f0-9]{64}$') { throw 'Registro de versão inválido. Nada foi removido.' }
        $identified = $true
        $maintenance = Join-Path (Join-Path $InstallRoot $current.directory) 'Manutencao.exe'
        $sourceMode = $current.PSObject.Properties.Name -contains 'mode' -and $current.mode -eq 'source'
        $null = Assert-SafeDirectory (Join-Path $InstallRoot $current.directory) -ManagedSource:$sourceMode
        if (Test-Path -LiteralPath $maintenance) {
            # The shell command is also available in packages published before
            # this uninstaller; it resolves dotenv using the bundled Python.
            $code = "import json,hashlib,os; from runtime.installation import resolve_data_dir; p=resolve_data_dir(); print(json.dumps({'data_root':str(p),'mutex_name':'Local\\RestauranteLocal-'+hashlib.sha256(os.path.normcase(str(p)).encode()).hexdigest()}))"
            $stdout = Join-Path ([IO.Path]::GetTempPath()) ('restaurante-uninstall-paths-' + [guid]::NewGuid().ToString('N') + '.json')
            $stderr = $stdout + '.error'
            try {
                $process = Start-Process -FilePath $maintenance -ArgumentList ('shell --no-imports --verbosity 0 -c "' + $code + '"') -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
                if ($process.ExitCode -eq 0) { Add-DataLocation (Get-Content -LiteralPath $stdout -Raw | ConvertFrom-Json) }
                elseif (-not $dataLocations.Count -and -not $DataRoot) { throw 'Não foi possível identificar os dados. Informe -DataRoot explicitamente. Nada foi removido.' }
            } finally {
                foreach ($temporary in @($stdout, $stderr)) { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
            }
        }
    }
    if (-not $identified) { throw 'Pasta sem identificação de instalação. Nada foi removido.' }
    if ($DataRoot) {
        $requestedData = Assert-SafeDirectory $DataRoot
        if ($dataLocations.Count -and -not @($dataLocations | Where-Object { $_.data_root -eq $requestedData }).Count) {
            throw 'DataRoot não corresponde aos dados registrados. Nada foi removido.'
        }
        if (-not $dataLocations.Count) { Add-DataLocation @{ data_root = $requestedData; mutex_name = (Get-MutexName $requestedData) } }
    }
    if (-not $dataLocations.Count) {
        if (Test-Path -LiteralPath $InstallRoot) { throw 'Dados não identificados. Informe -DataRoot para recuperar esta instalação incompleta.' }
        $defaultData = if ($env:LOCAL_WEIGHING_DATA_DIR) { $env:LOCAL_WEIGHING_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'RestauranteLocal' }
        $defaultData = Assert-SafeDirectory $defaultData
        Add-DataLocation @{ data_root = $defaultData; mutex_name = (Get-MutexName $defaultData) }
    }
    foreach ($location in $dataLocations) {
        $path = $location.data_root
        if ($path -eq $InstallRoot -or $path.StartsWith($InstallRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
            $InstallRoot.StartsWith($path + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Programa e dados precisam estar em pastas separadas para remover com segurança.' }
    }
    if (-not $ShortcutPath) { $ShortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Restaurante Local.lnk' }
    $ShortcutPath = [IO.Path]::GetFullPath($ShortcutPath)
    Write-Host "Programa a remover: $InstallRoot"
    foreach ($location in $dataLocations) { Write-Host "Dados e backups: $($location.data_root)" }
    if (-not $Yes) {
        if (-not $DeleteData) { $DeleteData = (Read-Host 'Apagar também banco, configurações, logs e TODOS os backups? Digite APAGAR; Enter preserva os dados') -ceq 'APAGAR' }
        Write-Host $(if ($DeleteData) { 'Os dados listados serão apagados permanentemente.' } else { 'Os dados listados serão preservados.' })
        if ((Read-Host 'Confirma a desinstalação? Digite S para continuar') -notmatch '^[sS]$') { Write-Host 'Cancelado. Nenhum arquivo foi removido.'; exit 0 }
    }
    if (Test-Path -LiteralPath $InstallRoot) {
        $createdLock = -not (Test-Path -LiteralPath $lockPath)
        $updateLock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    }
    foreach ($location in $dataLocations) {
        $created = $false
        $mutex = [Threading.Mutex]::new($false, $location.mutex_name, [ref]$created)
        if (-not $created) { $mutex.Dispose(); throw 'A aplicação está aberta. Use Encerrar aplicação e tente novamente. Nenhum arquivo foi removido.' }
        $mutexes += $mutex
    }
    $removalStarted = $true
    Set-Location -LiteralPath ([IO.Path]::GetTempPath())
    if (-not $DeleteData) {
        $preservedSettings = Join-Path $dataLocations[-1].data_root 'preserved-installation'
        foreach ($setting in @('.env', 'update-url.txt', 'source-settings.json')) {
            $original = Join-Path $InstallRoot $setting
            if (Test-Path -LiteralPath $original) {
                $null = Assert-SafeDirectory $preservedSettings
                $destination = Join-Path $preservedSettings $setting
                if ((Test-Path -LiteralPath $destination) -and ((Get-Item -LiteralPath $destination -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Configuração preservada com link: $destination" }
                New-Item -ItemType Directory -Path $preservedSettings -Force | Out-Null
                Copy-Item -LiteralPath $original -Destination $destination -Force
                Write-Host "Configuração preservada: $destination" -ForegroundColor Yellow
            }
        }
    }
    if (Test-Path -LiteralPath $ShortcutPath) {
        try {
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut($ShortcutPath)
            $launchArgument = [regex]::Match($shortcut.Arguments, '(?i)(?:^|\s)-File\s+"([^"]+)"(?:\s|$)')
            $expected = Normalize-Directory (Join-Path $InstallRoot 'Launch.ps1')
            if ($launchArgument.Success -and (Normalize-Directory $launchArgument.Groups[1].Value) -eq $expected) { Remove-Item -LiteralPath $ShortcutPath -Force }
            else { Write-Host "Atalho preservado: $ShortcutPath (aponta para outra instalação)." -ForegroundColor Yellow }
        } catch { $problems.Add("$ShortcutPath — $($_.Exception.Message)") }
    }
    if ($DeleteData) { foreach ($location in $dataLocations) { Remove-OwnedTree $location.data_root } }
    $recoveryFiles = @($infoPath, (Join-Path $InstallRoot 'Uninstall.ps1'), (Join-Path $InstallRoot 'Desinstalar.bat'))
    Remove-OwnedTree $InstallRoot (@($lockPath) + $recoveryFiles)
    if ($updateLock) { $updateLock.Dispose(); $updateLock = $null }
    if (Test-Path -LiteralPath $lockPath) { Remove-OwnedTree $lockPath }
    # Keep recovery metadata when any removal failed, so a retry still knows
    # custom data locations after the executable has already been removed.
    if (-not $problems.Count) { foreach ($recoveryFile in $recoveryFiles) { Remove-OwnedTree $recoveryFile } }
    Remove-OwnedTree $InstallRoot $recoveryFiles
    $remaining = @(Get-RemainingPaths $InstallRoot)
    if ($DeleteData) { foreach ($location in $dataLocations) { $remaining += @(Get-RemainingPaths $location.data_root) } }
    if ($remaining.Count -or $problems.Count) {
        Write-Host 'A desinstalação ficou incompleta. Estes arquivos/pastas permaneceram:' -ForegroundColor Yellow
        foreach ($path in $remaining) { Write-Host "  $path" }
        foreach ($problem in $problems) { Write-Host "  Falha: $problem" }
        $report = Join-Path ([IO.Path]::GetTempPath()) ('RestauranteLocal-desinstalacao-' + [guid]::NewGuid().ToString('N') + '.txt')
        @('Remoção incompleta', $remaining, $problems.ToArray()) | Out-File -LiteralPath $report -Encoding UTF8
        Write-Host "Relatório de pendências preservado: $report"
        $exitCode = 1
    } else { Write-Host 'Todos os arquivos da instalação foram removidos.' -ForegroundColor Green; $exitCode = 0 }
    if (-not $DeleteData) {
        Write-Host 'DADOS PRESERVADOS por sua escolha:' -ForegroundColor Yellow
        foreach ($location in $dataLocations) { if (Test-Path -LiteralPath $location.data_root) { Write-Host "  $($location.data_root) — banco, configurações, logs e backups." } }
    }
    foreach ($origin in $origins) { if (Test-Path -LiteralPath $origin) { Write-Host "Pacote de origem preservado fora da instalação: $origin" -ForegroundColor Yellow } }
    if (-not $PSScriptRoot.StartsWith($InstallRoot + '\', [StringComparison]::OrdinalIgnoreCase) -and $PSScriptRoot -ne $InstallRoot) {
        Write-Host "Pasta desta ferramenta preservada: $PSScriptRoot" -ForegroundColor Yellow
    }
    Write-Host 'ZIPs baixados pelo navegador, cópias manuais e atalhos criados fora do instalador não são rastreados nem removidos. Confira a pasta Downloads e suas cópias.'
    exit $exitCode
} catch {
    Write-Host ('Não foi possível concluir a desinstalação: ' + $_.Exception.Message) -ForegroundColor Red
    if ($removalStarted) { Write-Host "Confira o que restou em $InstallRoot e nas pastas de dados listadas." -ForegroundColor Yellow }
    exit 1
} finally {
    if ($updateLock) { $updateLock.Dispose() }
    if ($createdLock -and -not $removalStarted -and (Test-Path -LiteralPath $lockPath)) { Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue }
    foreach ($mutex in $mutexes) { $mutex.Dispose() }
}
