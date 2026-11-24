<#
.SYNOPSIS
  Stahne data aplikace Poznamky z PythonAnywhere (pres jeho API) do %USERPROFILE%\poznamky-migrace.
.DESCRIPTION
  Pred spustenim na PythonAnywhere:
    1. Web tab -> Disable (aby uz nevznikaly zapisy),
    2. v Bash konzoli:
       cd ~/self_mem/poznamky && python3 -c "import sqlite3;sqlite3.connect('notes.db').backup(sqlite3.connect('notes_export.db'))"
    3. Account -> API token -> vytvorit/zkopirovat token.
  Soubory obsahuji tajne udaje - adresar je mimo repozitar a po migraci ho smazte.
#>
[CmdletBinding()]
param(
    [string]$PaUser = 'miko73',
    [string]$PaHost = 'www.pythonanywhere.com'
)
. (Join-Path $PSScriptRoot 'common.ps1')

$token = Read-Secret 'PythonAnywhere API token'
if (-not $token) { throw 'Token je povinny.' }
New-Item -ItemType Directory -Force -Path $MigraceDir | Out-Null

$appDir = "/home/$PaUser/self_mem/poznamky"
$wsgi   = "/var/www/$($PaUser)_pythonanywhere_com_wsgi.py"
$items = @(
    @{ Remote = "$appDir/notes_export.db";   Local = 'notes.db';          Required = $true  },
    @{ Remote = "$appDir/google_auth.json";  Local = 'google_auth.json';  Required = $false },
    @{ Remote = "$appDir/anthropic_key.txt"; Local = 'anthropic_key.txt'; Required = $false },
    @{ Remote = "$appDir/secret_key.txt";    Local = 'secret_key.txt';    Required = $false },
    @{ Remote = $wsgi;                       Local = 'wsgi.py';           Required = $false }
)
$headers = @{ Authorization = "Token $token" }
foreach ($it in $items) {
    $target = Join-Path $MigraceDir $it.Local
    $uri = "https://$PaHost/api/v0/user/$PaUser/files/path$($it.Remote)"
    try {
        Invoke-WebRequest -Uri $uri -Headers $headers -OutFile $target -UseBasicParsing
        Write-Host ("   OK  {0,-18} {1,10:N0} B" -f $it.Local, (Get-Item -LiteralPath $target).Length)
    }
    catch {
        Remove-Item -LiteralPath $target -ErrorAction SilentlyContinue
        $msg = "   --  $($it.Local): nestazeno ($($_.Exception.Message))"
        if ($it.Required) { throw "$msg`nPovinny soubor chybi - zkontrolujte token a krok 2 (notes_export.db)." }
        Write-Host $msg -ForegroundColor Yellow
    }
}

# Promenne prostredi z WSGI souboru (os.environ['X'] = '...') -> poznamky.env pro VM
$wsgiFile = Join-Path $MigraceDir 'wsgi.py'
$envLines = @()
if (Test-Path -LiteralPath $wsgiFile) {
    $wsgiText = [IO.File]::ReadAllText($wsgiFile)
    $envLines = @(foreach ($m in [regex]::Matches($wsgiText, "(?m)^\s*os\.environ\[\s*['""](\w+)['""]\s*\]\s*=\s*['""]([^'""]*)['""]")) {
        "$($m.Groups[1].Value)='$($m.Groups[2].Value)'"
    })
    Remove-Item -LiteralPath $wsgiFile
} else {
    # API soubor z /var/www nevydalo -> hash zkopirovat z WSGI souboru (Web tab) rucne
    $hash = Read-Secret 'NOTES_PASSWORD_HASH z WSGI souboru (scrypt:...; Enter = preskocit)'
    if ($hash) {
        if ($hash -notmatch '^[A-Za-z0-9:$+/=._-]+$') { throw 'Hash ma neocekavany format.' }
        $envLines = @("NOTES_PASSWORD_HASH='$hash'")
    }
}
Write-LfFile (Join-Path $MigraceDir 'poznamky.env') (($envLines -join "`n") + "`n")
$names = @($envLines | ForEach-Object { ($_ -split '=', 2)[0] })
Write-Host "   promenne z WSGI: $($names -join ', ')"
if ($names -notcontains 'NOTES_PASSWORD_HASH') {
    Write-Host '   POZOR: NOTES_PASSWORD_HASH nenalezen - heslo nastavte v 00-priprava-vm.ps1.' -ForegroundColor Yellow
}

# Kontrola databaze (pokud je k dispozici Python)
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $check = @'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
print('   integrity_check:', db.execute('PRAGMA integrity_check').fetchone()[0])
for t in ('notes', 'scratchpad', 'changelog', 'kamera'):
    try:
        print(f'   {t:<11}', db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])
    except sqlite3.Error as e:
        print(f'   {t:<11}', 'chyba:', e)
'@
    $check | & $python.Source -I - (Join-Path $MigraceDir 'notes.db')
} else {
    Write-Host '   Python nenalezen - kontrola DB probehne az na VM.'
}
Write-Host "Data jsou v $MigraceDir. Dalsi krok: .\deploy\gcp\02-import-vm.ps1" -ForegroundColor Green
