# Create Cloud Build GitHub triggers for passanota-api
# Prerequisites: GitHub repo connected to Cloud Build (2nd gen)
# Usage: .\scripts\setup-cloud-build-trigger.ps1 -GitHubOwner OWNER -GitHubRepo passanota-api

param(
    [string]$Project = "caldas-projects-dev",
    [string]$Region = "us-central1",
    [Parameter(Mandatory = $true)]
    [string]$GitHubOwner,
    [Parameter(Mandatory = $true)]
    [string]$GitHubRepo,
    [string]$Branch = "main",
    [string]$FrontendUrl = "",
    [string]$SupabaseUrl = "",
    [string]$TaskHandlerBaseUrl = "",
    [string]$CloudTasksServiceAccount = ""
)

$ErrorActionPreference = "Stop"

gcloud config set project $Project

$ProjectNumber = gcloud projects describe $Project --format="value(projectNumber)"
if (-not $CloudTasksServiceAccount) {
    $CloudTasksServiceAccount = "${ProjectNumber}-compute@developer.gserviceaccount.com"
}

$MainSubstitutions = @(
    "_TAG=`$SHORT_SHA",
    "_FRONTEND_URL=$FrontendUrl",
    "_SUPABASE_URL=$SupabaseUrl",
    "_TASK_HANDLER_BASE_URL=$TaskHandlerBaseUrl",
    "_CLOUD_TASKS_SERVICE_ACCOUNT=$CloudTasksServiceAccount"
) -join ","

Write-Host "Creating main branch trigger (deploy)..."
gcloud builds triggers create github `
    --name="passanota-api-main" `
    --region=$Region `
    --repository="projects/$Project/locations/$Region/connections/CONNECTION/repositories/$GitHubOwner-$GitHubRepo" `
    --branch-pattern="^${Branch}$" `
    --build-config="cloudbuild.yaml" `
    --substitutions=$MainSubstitutions `
    2>&1 | Write-Host

Write-Host ""
Write-Host "NOTE: Update --repository with your Cloud Build 2nd gen connection path."
Write-Host "List connections: gcloud builds connections list --region=$Region"
Write-Host ""
Write-Host "Creating PR trigger (quality only)..."
gcloud builds triggers create github `
    --name="passanota-api-pr" `
    --region=$Region `
    --repository="projects/$Project/locations/$Region/connections/CONNECTION/repositories/$GitHubOwner-$GitHubRepo" `
    --pull-request-pattern="^${Branch}$" `
    --build-config="cloudbuild.pr.yaml" `
    2>&1 | Write-Host

Write-Host ""
Write-Host "Manual trigger creation (if connection path differs):"
Write-Host @"
gcloud builds triggers create github --name=passanota-api-main --region=$Region \\
  --repo-name=$GitHubRepo --repo-owner=$GitHubOwner \\
  --branch-pattern=^${Branch}$$ --build-config=cloudbuild.yaml \\
  --substitutions=_TAG=`$SHORT_SHA,_FRONTEND_URL=<url>,_SUPABASE_URL=<url>,_TASK_HANDLER_BASE_URL=<api-url>,_CLOUD_TASKS_SERVICE_ACCOUNT=$CloudTasksServiceAccount

gcloud builds triggers create github --name=passanota-api-pr --region=$Region \\
  --repo-name=$GitHubRepo --repo-owner=$GitHubOwner \\
  --pull-request-pattern=^${Branch}$$ --build-config=cloudbuild.pr.yaml
"@
