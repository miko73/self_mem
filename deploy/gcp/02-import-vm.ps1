<#
.SYNOPSIS
  Nahraje data stazena skriptem 01-export-pa.ps1 na VM pg-free a restartuje aplikaci.
  Puvodni DB na VM (pokud existuje) se odlozi do /var/lib/poznamky/backup.
#>
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'common.ps1')

if (-not (Test-Path -LiteralPath (Join-Path $MigraceDir 'notes.db'))) {
    throw "V $MigraceDir chybi notes.db - nejprve spustte 01-export-pa.ps1."
}
$names = @('notes.db', 'google_auth.json', 'anthropic_key.txt', 'secret_key.txt', 'poznamky.env' |
    Where-Object { Test-Path -LiteralPath (Join-Path $MigraceDir $_) })
$importSh = Join-Path $MigraceDir 'import_vm.sh'
Write-LfFile $importSh ([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'import_vm.sh')))
try {
    $remote = '/tmp/poznamky-import'
    Write-Host "== Nahravam na $GcpVm`: $($names -join ', ')"
    Invoke-Vm "rm -rf $remote && mkdir -m 700 $remote"
    Copy-ToVm $MigraceDir (@('import_vm.sh') + $names) $remote
    Invoke-Vm "sudo bash $remote/import_vm.sh $remote"
}
finally {
    Remove-Item -LiteralPath $importSh -ErrorAction SilentlyContinue
}
Write-Host ''
Write-Host 'Porovnejte pocty radku s vystupem 01-export-pa.ps1 a overte aplikaci v prohlizeci.' -ForegroundColor Green
Write-Host "Po overeni smazte $MigraceDir (obsahuje tajne udaje)."
