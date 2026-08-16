param(
    [switch]$NoBrowser,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$apiRoot = Join-Path $repoRoot "apps\api"
$webUrl = "http://127.0.0.1:5173"
$apiHealth = "http://127.0.0.1:8000/api/v1/health/ready"

function Stop-ProcessTree {
    param([int]$RootProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $RootProcessId" `
        -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -RootProcessId $child.ProcessId
    }
    Stop-Process -Id $RootProcessId -Force -ErrorAction SilentlyContinue
}

Set-Location $repoRoot

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot ".env"))) {
    Copy-Item -LiteralPath (Join-Path $repoRoot ".env.example") -Destination (Join-Path $repoRoot ".env")
}

if (-not $SkipInstall) {
    pnpm install --frozen-lockfile
    uv sync --project $apiRoot --frozen
}

New-Item -ItemType Directory -Path (Join-Path $repoRoot "data") -Force | Out-Null
$logRoot = Join-Path $repoRoot "data\logs"
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

uv run --project $apiRoot alembic -c (Join-Path $apiRoot "alembic.ini") upgrade head

$pnpmExecutable = (Get-Command "pnpm.cmd" -ErrorAction Stop).Source
$pythonExecutable = Join-Path $apiRoot ".venv\Scripts\python.exe"

$api = Start-Process -FilePath $pythonExecutable -ArgumentList @(
    "-m", "veris_api"
) -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logRoot "api.out.log") `
    -RedirectStandardError (Join-Path $logRoot "api.err.log")

$web = Start-Process -FilePath $pnpmExecutable -ArgumentList @(
    "--filter", "@thesos/web", "dev", "--host", "127.0.0.1", "--port", "5173", "--strictPort"
) -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logRoot "web.out.log") `
    -RedirectStandardError (Join-Path $logRoot "web.err.log")

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($api.HasExited) {
            throw "Thesos API stopped during startup. Check data\logs\api.err.log."
        }
        if ($web.HasExited) {
            throw "Thesos web app stopped during startup. Check data\logs\web.err.log."
        }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $apiHealth -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if (-not $ready) {
        throw "Thesos API did not become ready."
    }

    if (-not $NoBrowser) {
        Start-Process $webUrl
    }

    Write-Host "Thesos is running at $webUrl"
    Write-Host "Press Ctrl+C to stop both services."
    Wait-Process -Id $api.Id, $web.Id
} finally {
    foreach ($process in @($api, $web)) {
        if ($process) {
            Stop-ProcessTree -RootProcessId $process.Id
        }
    }
}
