#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-caldas-projects-dev}"
TAG="${TAG:-${1:-latest}}"

gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config=cloudbuild.yaml \
  --substitutions="_TAG=${TAG}" \
  .
