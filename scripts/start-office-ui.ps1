param(
  [int]$ApiPort = 3002,
  [int]$UiPort = 7777
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
  $backendUrl = "http://127.0.0.1:$ApiPort"
  $uiUrl = "http://127.0.0.1:$UiPort"

  $env:VSCODE_DEBUG = "1"
  $env:SERVER_URL = $backendUrl
  $env:VITE_PROXY_URL = $backendUrl
  $env:VITE_USE_LOCAL_PROXY = "true"
  $env:VITE_SITE_URL = $uiUrl

  Write-Host "Starting Eigent browser UI at $uiUrl"
  Write-Host "Using backend API at $backendUrl"
  npm.cmd run dev -- --host 127.0.0.1 --port $UiPort
} finally {
  Pop-Location
}
