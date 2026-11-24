<#
.SYNOPSIS
  Nasadi aktualni verzi z GitHubu (git pull) na VM pg-free a restartuje aplikaci.
  Zmeny musi byt nejdriv pushnute do origin/master.
#>
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'common.ps1')
$cmd = 'set -e; cd /opt/self_mem && sudo git pull --ff-only && ' +
       'sudo venv/bin/pip install -q -r poznamky/requirements.txt gunicorn && ' +
       'sudo systemctl restart poznamky && sleep 3 && systemctl is-active poznamky && ' +
       "curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8000/login"
Invoke-Vm $cmd
Write-Host 'Aktualizace hotova.' -ForegroundColor Green
