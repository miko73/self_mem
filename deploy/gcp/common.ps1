# Spolecne funkce pro nasazeni Poznamek na Google Cloud VM (Windows PowerShell 5.1+).
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:GcpProject = 'pg-free-michal'
$script:GcpZone    = 'us-central1-a'
$script:GcpVm      = 'pg-free'
$script:GcpUser    = 'michal_kocandrle'
$script:GcpTarget  = "$($script:GcpUser)@$($script:GcpVm)"
$script:MigraceDir = Join-Path $env:USERPROFILE 'poznamky-migrace'

function Get-Gcloud {
    $candidates = @(
        $env:GCLOUD_PATH,
        "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "${env:ProgramFiles(x86)}\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "$env:ProgramFiles\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "$env:USERPROFILE\tools\google-cloud-sdk\bin\gcloud.cmd",
        'C:\dev\mikoucto\tools\_download\gcloud-portable\google-cloud-sdk\bin\gcloud.cmd'
    )
    $found = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $found) {
        $command = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
        if ($command) { $found = $command.Source }
    }
    if (-not $found) { throw 'Chybi gcloud.cmd. Nainstalujte Google Cloud SDK nebo nastavte GCLOUD_PATH.' }
    return $found
}

function Invoke-Gcloud {
    $gcloud = Get-Gcloud
    & $gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud skoncil chybou $LASTEXITCODE ($($args[0..2] -join ' '))." }
}

# Spusti prikaz na VM (bash). Vystup jde do konzole.
function Invoke-Vm([string]$Command) {
    Invoke-Gcloud compute ssh $script:GcpTarget "--project=$($script:GcpProject)" "--zone=$($script:GcpZone)" "--command=$Command"
}

# Zkopiruje soubory z lokalniho adresare do adresare na VM (pres gcloud compute scp).
# Predavaji se relativni nazvy: absolutni cestu 'C:\...' by gcloud cetl jako 'instance:cesta'.
function Copy-ToVm([string]$LocalDir, [string[]]$Names, [string]$RemoteDir) {
    Push-Location -LiteralPath $LocalDir
    try {
        Invoke-Gcloud compute scp @Names "$($script:GcpTarget):$RemoteDir" "--project=$($script:GcpProject)" "--zone=$($script:GcpZone)"
    }
    finally { Pop-Location }
}

function Read-Secret([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

# Zapise text jako UTF-8 bez BOM s LF konci radku (pro soubory ctene na Linuxu).
function Write-LfFile([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, ($Text -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding($false)))
}
