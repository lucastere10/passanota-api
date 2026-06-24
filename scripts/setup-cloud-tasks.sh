#!/usr/bin/env bash
# Setup Cloud Tasks queues and IAM for passanota-api
# Usage: ./scripts/setup-cloud-tasks.sh [project] [region] [service]

set -euo pipefail

PROJECT="${1:-caldas-projects-dev}"
REGION="${2:-us-central1}"
SERVICE="${3:-passanota-api}"

gcloud config set project "$PROJECT"
gcloud services enable cloudtasks.googleapis.com

create_or_update_queue() {
  local name="$1"
  local attempts="$2"
  local concurrency="$3"
  if gcloud tasks queues describe "$name" --location="$REGION" &>/dev/null; then
    echo "Updating queue $name..."
    gcloud tasks queues update "$name" \
      --location="$REGION" \
      --max-attempts="$attempts" \
      --max-concurrent-dispatches="$concurrency"
  else
    echo "Creating queue $name..."
    gcloud tasks queues create "$name" \
      --location="$REGION" \
      --max-attempts="$attempts" \
      --max-concurrent-dispatches="$concurrency"
  fi
}

create_or_update_queue invoice-processing 3 5
create_or_update_queue email-delivery 5 10

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
TASKS_SA="service-${PROJECT_NUMBER}@gcp-sa-cloudtasks.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/cloudtasks.enqueuer" \
  --quiet

gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${TASKS_SA}" \
  --role="roles/run.invoker" \
  --quiet

echo ""
echo "Done. Set on Cloud Run:"
echo "  CLOUD_TASKS_ENABLED=true"
echo "  GCP_PROJECT=$PROJECT"
echo "  GCP_LOCATION=$REGION"
echo "  CLOUD_TASKS_SERVICE_ACCOUNT=$COMPUTE_SA"
echo "  TASK_HANDLER_BASE_URL=<your-cloud-run-api-url>"
