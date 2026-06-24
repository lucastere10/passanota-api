param(
    [string]$Tag = $(if ($env:TAG) { $env:TAG } else { "latest" })
)

$ErrorActionPreference = "Stop"

$ProjectId = if ($env:PROJECT_ID) { $env:PROJECT_ID } else { "caldas-projects-dev" }
$Root = Split-Path -Parent $PSScriptRoot

Push-Location $Root
try {
    gcloud builds submit `
        --project=$ProjectId `
        --config=cloudbuild.yaml `
        --substitutions="_TAG=$Tag" `
        .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
