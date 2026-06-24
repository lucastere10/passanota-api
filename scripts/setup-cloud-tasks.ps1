# Setup Cloud Tasks queues and IAM for passanota-api
# Usage: .\scripts\setup-cloud-tasks.ps1 [-Project caldas-projects-dev] [-Region us-central1]

param(
    [string]$Project = "caldas-projects-dev",
    [string]$Region = "us-central1",
    [string]$ServiceName = "passanota-api"
)

$ErrorActionPreference = "Continue"

Write-Host "Setting project to $Project..."
gcloud config set project $Project

Write-Host "Enabling Cloud Tasks API..."
gcloud services enable cloudtasks.googleapis.com

Write-Host "Creating invoice-processing queue..."
gcloud tasks queues create invoice-processing `
    --location=$Region `
    --max-attempts=3 `
    --max-concurrent-dispatches=5 `
    2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Queue invoice-processing may already exist, updating..."
    gcloud tasks queues update invoice-processing `
        --location=$Region `
        --max-attempts=3 `
        --max-concurrent-dispatches=5
}

Write-Host "Creating email-delivery queue..."
gcloud tasks queues create email-delivery `
    --location=$Region `
    --max-attempts=5 `
    --max-concurrent-dispatches=10 `
    2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Queue email-delivery may already exist, updating..."
    gcloud tasks queues update email-delivery `
        --location=$Region `
        --max-attempts=5 `
        --max-concurrent-dispatches=10
}

$ProjectNumber = gcloud projects describe $Project --format="value(projectNumber)"
$ComputeSa = "${ProjectNumber}-compute@developer.gserviceaccount.com"
$TasksSa = "service-${ProjectNumber}@gcp-sa-cloudtasks.iam.gserviceaccount.com"

Write-Host "Granting cloudtasks.enqueuer to $ComputeSa..."
gcloud projects add-iam-policy-binding $Project `
    --member="serviceAccount:$ComputeSa" `
    --role="roles/cloudtasks.enqueuer" `
    --quiet

Write-Host "Granting run.invoker to $TasksSa on $ServiceName..."
gcloud run services add-iam-policy-binding $ServiceName `
    --region=$Region `
    --member="serviceAccount:$TasksSa" `
    --role="roles/run.invoker" `
    --quiet

Write-Host ""
Write-Host "Done. Set these env vars on Cloud Run:"
Write-Host "  CLOUD_TASKS_ENABLED=true"
Write-Host "  GCP_PROJECT=$Project"
Write-Host "  GCP_LOCATION=$Region"
Write-Host "  CLOUD_TASKS_SERVICE_ACCOUNT=$ComputeSa"
Write-Host "  TASK_HANDLER_BASE_URL=<your-cloud-run-api-url>"
