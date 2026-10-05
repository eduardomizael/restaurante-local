param([string]$InstallRoot = $PSScriptRoot, [switch]$SkipUpdate, [string]$RuntimeArguments = '')
$ErrorActionPreference = 'Stop'
try {
    if (-not $SkipUpdate) {
        $updateScript = Join-Path $InstallRoot 'Update.ps1'
        $stdout = Join-Path $InstallRoot 'update.log'
        $stderr = Join-Path $InstallRoot 'update-error.log'
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $updateScript + '" -InstallRoot "' + $InstallRoot + '" -CheckOnStart'
        $updater = Start-Process -FilePath powershell.exe -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        # Download failures keep the installed build usable offline.
    }
    if (Test-Path -LiteralPath (Join-Path $InstallRoot 'update-failed.txt')) {
        throw 'A atualização dos dados falhou. Execute Atualizar.bat antes de abrir. Confira o backup e update.log.'
    }
    $updateLock = [IO.File]::Open((Join-Path $InstallRoot 'update.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $updateLock.Dispose()
    $record = Get-Content -LiteralPath (Join-Path $InstallRoot 'current.json') -Raw | ConvertFrom-Json
    if ($record.directory -notmatch '^versions/[a-f0-9]{64}$') { throw 'Registro de versão inválido.' }
    $appDirectory = Join-Path $InstallRoot $record.directory
    $executable = Join-Path $appDirectory 'RestauranteLocal.exe'
    if (-not (Test-Path -LiteralPath $executable)) { throw 'Programa ausente. Execute Atualizar.bat.' }
    if ($RuntimeArguments) {
        $application = Start-Process -FilePath $executable -ArgumentList $RuntimeArguments -WorkingDirectory $appDirectory -WindowStyle Hidden -PassThru
    } else {
        $application = Start-Process -FilePath $executable -WorkingDirectory $appDirectory -WindowStyle Hidden -PassThru
    }
    Write-Output $application.Id
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Restaurante Local') | Out-Null
    exit 1
}
