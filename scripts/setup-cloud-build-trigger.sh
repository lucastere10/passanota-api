#!/usr/bin/env bash
# Create Cloud Build GitHub triggers for passanota-api
# Usage: ./scripts/setup-cloud-build-trigger.sh OWNER REPO [project] [region]

set -euo pipefail

OWNER="${1:?GitHub owner required}"
REPO="${2:?GitHub repo required}"
PROJECT="${3:-caldas-projects-dev}"
REGION="${4:-us-central1}"
BRANCH="${BRANCH:-main}"

gcloud config set project "$PROJECT"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Create triggers via Cloud Console or gcloud after connecting GitHub."
echo ""
echo "Main (deploy on push to $BRANCH):"
echo "  build-config: cloudbuild.yaml"
echo "  substitutions: _TAG=\$SHORT_SHA,_FRONTEND_URL=...,_SUPABASE_URL=...,_TASK_HANDLER_BASE_URL=...,_CLOUD_TASKS_SERVICE_ACCOUNT=$COMPUTE_SA"
echo ""
echo "PR (quality checks):"
echo "  build-config: cloudbuild.pr.yaml"
echo ""
echo "Example (1st gen GitHub app):"
cat <<EOF
gcloud builds triggers create github \\
  --name=passanota-api-main \\
  --repo-name=$REPO \\
  --repo-owner=$OWNER \\
  --branch-pattern=^${BRANCH}\$ \\
  --build-config=cloudbuild.yaml \\
  --substitutions=_TAG=\$SHORT_SHA,_CLOUD_TASKS_SERVICE_ACCOUNT=$COMPUTE_SA

gcloud builds triggers create github \\
  --name=passanota-api-pr \\
  --repo-name=$REPO \\
  --repo-owner=$OWNER \\
  --pull-request-pattern=^${BRANCH}\$ \\
  --build-config=cloudbuild.pr.yaml
EOF
