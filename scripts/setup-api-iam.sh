#!/usr/bin/env bash
# Grant Cloud Run invoker on passanota-api to passanota-web and Cloud Tasks
# Usage: ./scripts/setup-api-iam.sh [project] [region] [api-service] [web-service]

set -euo pipefail

PROJECT="${1:-caldas-projects-dev}"
REGION="${2:-us-central1}"
API_SERVICE="${3:-passanota-api}"
WEB_SERVICE="${4:-passanota-web}"

gcloud config set project "$PROJECT"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
TASKS_SA="service-${PROJECT_NUMBER}@gcp-sa-cloudtasks.iam.gserviceaccount.com"

WEB_SA="$(gcloud run services describe "$WEB_SERVICE" \
  --region="$REGION" \
  --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || true)"
if [[ -z "$WEB_SA" ]]; then
  WEB_SA="$COMPUTE_SA"
  echo "Using default compute SA for web: $WEB_SA"
else
  echo "Using web service account: $WEB_SA"
fi

gcloud run services add-iam-policy-binding "$API_SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${TASKS_SA}" \
  --role="roles/run.invoker" \
  --quiet

gcloud run services add-iam-policy-binding "$API_SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${WEB_SA}" \
  --role="roles/run.invoker" \
  --quiet

echo ""
echo "Done. passanota-api accepts invocations from:"
echo "  - Cloud Tasks: $TASKS_SA"
echo "  - Frontend:    $WEB_SA"
