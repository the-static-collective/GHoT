# GHoT Garden Router: run once, or register an optional 2-hour user-scoped Windows task.
# Credentials are read from the signed-in user's GitHub CLI at runtime only.
param(
  [ValidateSet('Sweep','Context','Install','Status','Remove')][string]$Action = 'Sweep',
  [string]$Query = 'HUMKIN',
  [string]$Output = "$HOME\.ghot\garden-router\selected-context.json"
)
$ErrorActionPreference = 'Stop'
$TaskName = 'GHoT Garden Router'
$Router = Join-Path $PSScriptRoot 'router.py'
$Routes = Join-Path $PSScriptRoot 'routes.json'

if ($Action -eq 'Status') {
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($task) { $task | Select-Object TaskName,State; Get-ScheduledTaskInfo -TaskName $TaskName }
  else { Write-Output 'GHoT Garden Router is not scheduled.' }
  exit
}
if ($Action -eq 'Remove') {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
  Write-Output 'Removed only the GHoT Garden Router scheduled task. Private state remains.'
  exit
}
if ($Action -eq 'Install') {
  $Gh = Get-Command 'gh' -ErrorAction SilentlyContinue
  if (-not $Gh) { throw 'Install GitHub CLI and sign in: gh auth login (requires private-repo read permission).' }
  & $Gh.Source auth status | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Sign in to GitHub CLI with gh auth login first.' }
  $PowerShell = (Get-Process -Id $PID).Path
  $taskAction = New-ScheduledTaskAction -Execute $PowerShell -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Action Sweep')
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Days 365)
  $principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $trigger -Principal $principal -Description 'Private GHoT garden scan: reads authorized GitHub repos and writes local HELD receipts only.' -Force | Out-Null
  Write-Output 'Installed a two-hour task for the current logged-in user; inspect with -Action Status. Reinstall before the one-year repetition window expires.'
  exit
}
$Py = Get-Command 'python' -ErrorAction SilentlyContinue
if (-not $Py) { throw 'Python 3.10+ is required.' }
if ($Action -eq 'Context') {
  & $Py.Source $Router context --query $Query --out $Output
  if ($LASTEXITCODE -ne 0) { throw "Local context export failed (exit $LASTEXITCODE)." }
  Write-Output "Private context: $Output"
  exit
}
$Gh = Get-Command 'gh' -ErrorAction SilentlyContinue
if (-not $Gh) { throw 'GitHub CLI (gh) required for ephemeral authorized token: gh auth login' }
try {
  $env:GH_TOKEN = (& $Gh.Source auth token)
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($env:GH_TOKEN)) {
    throw 'Could not retrieve a GitHub token from local gh login.'
  }
  & $Py.Source $Router sweep --owner the-static-collective --routes $Routes
  if ($LASTEXITCODE -ne 0) { throw "Garden scan returned coverage errors (exit $LASTEXITCODE)." }
} finally {
  Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
}
