param(
  [switch]$Start,
  [switch]$Recreate,
  [int]$ApiPort
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$serverDir = Join-Path $repoRoot "server"
$envPath = Join-Path $serverDir ".env.office"
$examplePath = Join-Path $serverDir ".env.office.example"

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [switch]$Quiet
  )

  $oldErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $output = & $FilePath @ArgumentList 2>&1
    $exitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $oldErrorActionPreference
  }

  if ($exitCode -ne 0) {
    $output | ForEach-Object { Write-Host $_ }
    throw "$FilePath $($ArgumentList -join ' ') failed with exit code $exitCode"
  }
  if (-not $Quiet) {
    $output | ForEach-Object { Write-Host $_ }
  }
}

function New-Secret {
  param([int]$Bytes = 32)
  $buffer = New-Object byte[] $Bytes
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($buffer)
  } finally {
    $rng.Dispose()
  }
  return [Convert]::ToBase64String($buffer).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

if ($PSBoundParameters.ContainsKey("ApiPort")) {
  $env:EIGENT_API_PORT = $ApiPort.ToString()
}

if ((Test-Path -LiteralPath $envPath) -and -not $Recreate) {
  Write-Host "Using existing server\.env.office"
} else {
  if (-not (Test-Path -LiteralPath $examplePath)) {
    throw "Missing template: $examplePath"
  }

  $content = Get-Content -LiteralPath $examplePath -Raw
  $content = $content.Replace("replace-with-generated-postgres-password", (New-Secret 24))
  $content = $content.Replace("replace-with-generated-redis-password", (New-Secret 24))
  $content = $content.Replace("replace-with-generated-jwt-secret", (New-Secret 48))
  $content = $content.Replace("replace-with-generated-share-secret", (New-Secret 48))
  $content = $content.Replace("replace-with-generated-share-salt", (New-Secret 24))
  Set-Content -LiteralPath $envPath -Value $content -Encoding UTF8
  Write-Host "Created server\.env.office with generated local secrets"
}

Invoke-Checked "docker" @("compose", "version") -Quiet

$commit = & git -C $repoRoot log -1 --format=%H -- server/ 2>$null
if ($LASTEXITCODE -eq 0 -and $commit) {
  $env:EIGENT_SERVER_GIT_COMMIT = $commit.Trim()
}

$officeApiPort = $env:EIGENT_API_PORT
if (-not $officeApiPort) {
  $envFilePort = Select-String -LiteralPath $envPath -Pattern '^EIGENT_API_PORT=(.+)$' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($envFilePort) {
    $officeApiPort = $envFilePort.Matches[0].Groups[1].Value.Trim()
  }
}
if (-not $officeApiPort) {
  $officeApiPort = "3001"
}

Push-Location $serverDir
try {
  Invoke-Checked "docker" @("compose", "--env-file", ".env.office", "-f", "docker-compose.office.yml", "config") -Quiet
  Write-Host "Office sandbox configuration is valid."

  if ($Start) {
    Invoke-Checked "docker" @("compose", "--env-file", ".env.office", "-f", "docker-compose.office.yml", "up", "--build", "-d")
    Write-Host "Office sandbox is starting at http://127.0.0.1:$officeApiPort"
  } else {
    Write-Host "Run with -Start when you want to build and start the containers."
  }
} finally {
  Pop-Location
}
