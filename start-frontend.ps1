$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root "Frontend"

Push-Location $frontend
try {
    npm run dev
}
finally {
    Pop-Location
}
