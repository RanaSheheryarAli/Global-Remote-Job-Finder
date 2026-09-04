param(
    [string]$LanIp
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
$alembicExe = Join-Path $backendDir ".venv\Scripts\alembic.exe"
$logDir = Join-Path $projectRoot ".local-logs"

if (-not $LanIp) {
    $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Where-Object { $_.NextHop -ne "0.0.0.0" } |
        Sort-Object RouteMetric |
        Select-Object -First 1
    if ($defaultRoute) {
        $LanIp = Get-NetIPAddress -InterfaceIndex $defaultRoute.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "169.254.*" } |
            Select-Object -ExpandProperty IPAddress -First 1
    }
}

if (-not $LanIp) {
    throw "No active LAN IPv4 address was found. Pass one with -LanIp."
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Backend virtual environment was not found at $pythonExe"
}
if (-not (Test-Path -LiteralPath $alembicExe)) {
    throw "Alembic was not found at $alembicExe"
}

foreach ($port in 3000, 8000) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $port is already in use. Stop the existing local service before running this script."
    }
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# These overrides belong only to local LAN development. Render and Vercel continue
# to use the environment variables configured in their own dashboards.
$env:APP_ENV = "development"
$env:CORS_ORIGINS = "[`"http://localhost:3000`",`"http://127.0.0.1:3000`",`"http://${LanIp}:3000`"]"
$databaseLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
if (-not $databaseLine) {
    throw "DATABASE_URL was not found in $envFile"
}
$env:DATABASE_URL = $databaseLine.Substring("DATABASE_URL=".Length) -replace '@postgres:', '@127.0.0.1:'

Push-Location $backendDir
try {
    & $alembicExe upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed."
    }
} finally {
    Pop-Location
}

$backend = Start-Process -FilePath $pythonExe `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload") `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "backend.out.log") `
    -RedirectStandardError (Join-Path $logDir "backend.err.log") `
    -PassThru

$env:INTERNAL_API_BASE_URL = "http://127.0.0.1:8000"
$env:NEXT_PUBLIC_API_BASE_URL = "http://${LanIp}:8000"
$frontend = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--hostname", "0.0.0.0") `
    -WorkingDirectory $frontendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "frontend.out.log") `
    -RedirectStandardError (Join-Path $logDir "frontend.err.log") `
    -PassThru

Write-Output "Backend PID: $($backend.Id)"
Write-Output "Frontend PID: $($frontend.Id)"
Write-Output "This laptop: http://localhost:3000"
Write-Output "Other laptop: http://${LanIp}:3000"
