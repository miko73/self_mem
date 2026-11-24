<#
.SYNOPSIS
  Pripravi VM pg-free pro aplikaci Poznamky: firewall 80/443, Caddy, gunicorn, DuckDNS, zalohy.
.EXAMPLE
  .\deploy\gcp\00-priprava-vm.ps1 -Subdomena mojepoznamky
  (aplikace pak bezi na https://mojepoznamky.duckdns.org)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9-]+$')][string]$Subdomena,
    [switch]$BezFirewallu
)
. (Join-Path $PSScriptRoot 'common.ps1')
$domain = "$Subdomena.duckdns.org"

if (-not $BezFirewallu) {
    Write-Host '== Firewall: tcp 80/443 pro VM s tagem web (5432 zustava zavreny)'
    $gcloud = Get-Gcloud
    & $gcloud compute firewall-rules describe allow-web "--project=$GcpProject" --format='value(name)' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Gcloud compute firewall-rules create allow-web "--project=$GcpProject" --direction=INGRESS `
            --action=ALLOW --rules=tcp:80,tcp:443 --source-ranges=0.0.0.0/0 --target-tags=web
    } else { Write-Host '   pravidlo allow-web uz existuje' }
    Invoke-Gcloud compute instances add-tags $GcpVm "--project=$GcpProject" "--zone=$GcpZone" --tags=web
}

$token = Read-Secret 'DuckDNS token (z https://www.duckdns.org po prihlaseni)'
if (-not $token) { throw 'Token je povinny.' }
$password = Read-Secret 'Heslo do aplikace (Enter = prevzit pozdeji z PythonAnywhere)'

function Format-BashValue([string]$v) { "'" + ($v -replace "'", "'\''") + "'" }

$stage = Join-Path ([IO.Path]::GetTempPath()) ("poznamky-deploy-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $files = 'setup_vm.sh', 'Caddyfile', 'poznamky.service', 'duckdns.sh', 'duckdns.service', 'duckdns.timer',
             'backup.sh', 'poznamky-backup.service', 'poznamky-backup.timer'
    foreach ($f in $files) {
        Write-LfFile (Join-Path $stage $f) ([IO.File]::ReadAllText((Join-Path $PSScriptRoot $f)))
    }
    $envText = "DOMAIN=$(Format-BashValue $domain)`nDUCKDNS_SUBDOMAIN=$(Format-BashValue $Subdomena)`n" +
               "DUCKDNS_TOKEN=$(Format-BashValue $token)`n"
    if ($password) { $envText += "NOTES_PASSWORD=$(Format-BashValue $password)`n" }
    Write-LfFile (Join-Path $stage 'setup.env') $envText

    $remote = '/tmp/poznamky-deploy'
    Write-Host "== Nahravam soubory na $GcpVm"
    Invoke-Vm "rm -rf $remote && mkdir -m 700 $remote"
    Copy-ToVm $stage @(Get-ChildItem -LiteralPath $stage -File | ForEach-Object Name) $remote
    Write-Host '== Instalace na VM (muze trvat nekolik minut)'
    Invoke-Vm "sudo bash $remote/setup_vm.sh $remote"
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host "Overeni: https://$domain/login" -ForegroundColor Green
Write-Host 'Prvni certifikat muze trvat 1-2 minuty. Data prenese 01-export-pa.ps1 a 02-import-vm.ps1.'
