# GHoT local garden sweep. No token is written to disk or passed as a command-line argument.
# Run from a trusted Windows account signed into GitHub CLI (`gh auth login`).
param(
  [ValidateSet('Sweep','Context')][string]$Action = 'Sweep',
  [string]$Query = 'HUMKIN',
  [string]$Output = "$HOME\.ghot\garden-router\selected-context.json"
)
$ErrorActionPreference = 'Stop'
$Py = Get-Command 'python' -ErrorAction SilentlyContinue
if (-not $Py) { throw 'Python 3.10+ is required.' }
$Router = Join-Path $PSScriptRoot 'router.py'
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
  & $Py.Source $Router sweep --owner the-static-collective
  if ($LASTEXITCODE -ne 0) { throw "Garden scan returned coverage errors (exit $LASTEXITCODE)." }
} finally {
  Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
}
