# Grant Cloud Run invoker on passanota-api to passanota-web and Cloud Tasks
# Usage: .\scripts\setup-api-iam.ps1 [-Project caldas-projects-dev] [-Region us-central1]

param(
    [string]$Project = "caldas-projects-dev",
    [string]$Region = "us-central1",
    [string]$ApiService = "passanota-api",
    [string]$WebService = "passanota-web",
    [string]$WebServiceAccount = ""
)

$ErrorActionPreference = "Continue"

Write-Host "Setting project to $Project..."
gcloud config set project $Project

$ProjectNumber = gcloud projects describe $Project --format="value(projectNumber)"
$ComputeSa = "${ProjectNumber}-compute@developer.gserviceaccount.com"
$TasksSa = "service-${ProjectNumber}@gcp-sa-cloudtasks.iam.gserviceaccount.com"

if (-not $WebServiceAccount) {
    $WebServiceAccount = gcloud run services describe $WebService `
        --region=$Region `
        --format="value(spec.template.spec.serviceAccountName)" 2>$null
    if (-not $WebServiceAccount) {
        $WebServiceAccount = $ComputeSa
        Write-Host "Web service not found or no custom SA; using default compute SA: $WebServiceAccount"
    } else {
        Write-Host "Using web service account: $WebServiceAccount"
    }
}

Write-Host "Granting run.invoker to Cloud Tasks SA ($TasksSa)..."
gcloud run services add-iam-policy-binding $ApiService `
    --region=$Region `
    --member="serviceAccount:$TasksSa" `
    --role="roles/run.invoker" `
    --quiet

Write-Host "Granting run.invoker to web SA ($WebServiceAccount)..."
gcloud run services add-iam-policy-binding $ApiService `
    --region=$Region `
    --member="serviceAccount:$WebServiceAccount" `
    --role="roles/run.invoker" `
    --quiet

Write-Host ""
Write-Host "Done. passanota-api accepts invocations from:"
Write-Host "  - Cloud Tasks: $TasksSa"
Write-Host "  - Frontend:    $WebServiceAccount"
