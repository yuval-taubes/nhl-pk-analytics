$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$snapshotDir = Join-Path $root "Frontend\public\data"
$snapshotPath = Join-Path $snapshotDir "dashboard.json"

New-Item -ItemType Directory -Force -Path $snapshotDir | Out-Null

$api = Start-Process -FilePath dotnet -ArgumentList @(
    "run",
    "--no-build",
    "--project",
    "NhlPkApi\NhlPkApi.csproj",
    "--urls",
    "http://localhost:5080"
) -WorkingDirectory $root -PassThru -WindowStyle Hidden

try {
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        try {
            Invoke-RestMethod -Uri "http://localhost:5080/api/health" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Milliseconds 750
        }
    }

    if (-not $ready) {
        throw "NhlPkApi did not become ready on http://localhost:5080."
    }

    $response = Invoke-WebRequest -Uri "http://localhost:5080/api/analytics/dashboard" -UseBasicParsing
    $response.Content | Set-Content -LiteralPath $snapshotPath -Encoding UTF8
    Write-Host "Wrote $snapshotPath"
}
finally {
    if ($api -and -not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
}
