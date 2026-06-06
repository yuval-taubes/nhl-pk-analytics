$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$snapshotDir = Join-Path $root "Frontend\public\data"
$snapshotPath = Join-Path $snapshotDir "dashboard.json"

New-Item -ItemType Directory -Force -Path $snapshotDir | Out-Null

$api = Start-Process -FilePath dotnet -ArgumentList @(
    "run",
    "--configuration",
    "Release",
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

    $response = Invoke-WebRequest -Uri "http://localhost:5080/api/analytics/v2/dashboard" -UseBasicParsing
    $payloadBytes = [Text.Encoding]::UTF8.GetByteCount($response.Content)
    if ($payloadBytes -gt 1048576) {
        $sizeMb = [Math]::Round($payloadBytes / 1MB, 2)
        throw "Snapshot payload is $sizeMb MB. Refusing to write a GitHub Pages snapshot over 1 MB."
    }
    $response.Content | Set-Content -LiteralPath $snapshotPath -Encoding UTF8
    $sizeKb = [Math]::Round((Get-Item -LiteralPath $snapshotPath).Length / 1KB, 1)
    Write-Host "Wrote $snapshotPath ($sizeKb KB)"
}
finally {
    if ($api -and -not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
}
