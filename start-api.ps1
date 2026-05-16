$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Join-Path $root "NhlPkApi\NhlPkApi.csproj"

dotnet run --project $project --urls "http://localhost:5080"
