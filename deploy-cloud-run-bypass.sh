#!/usr/bin/env bash
# Playground deploy: brings the service up FAST with DEV_AUTH_BYPASS=true.
# No OAuth secrets, no app-level login. Good for verifying the wiring.
# When you're ready to lock down, run deploy-cloud-run.sh instead.
#
# Required env:
#   PROJECT_ID
# Optional env (defaults shown):
#   REGION=me-central2
#   SERVICE_NAME=vm-sheet-transformer
#   REPOSITORY=vm-sheet-transformer
#   ALLOW_UNAUTH=true        # set to "false" to require Cloud Run IAM invoker

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID env var is required}"
REGION="${REGION:-me-central2}"
SERVICE_NAME="${SERVICE_NAME:-vm-sheet-transformer}"
REPOSITORY="${REPOSITORY:-vm-sheet-transformer}"
ALLOW_UNAUTH="${ALLOW_UNAUTH:-true}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_EMAIL:-${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "==> Project:   ${PROJECT_ID}"
echo "==> Region:    ${REGION}"
echo "==> Service:   ${SERVICE_NAME}"
echo "==> Image:     ${IMAGE_URI}"
echo "==> Auth:      DEV_AUTH_BYPASS=true (playground mode)"
echo "==> Public:    --allow-unauthenticated=${ALLOW_UNAUTH}"
echo

gcloud config set project "${PROJECT_ID}" >/dev/null

echo "==> Enabling APIs (idempotent)..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    --project="${PROJECT_ID}"

if ! gcloud artifacts repositories describe "${REPOSITORY}" --location="${REGION}" >/dev/null 2>&1; then
    echo "==> Creating Artifact Registry repo ${REPOSITORY}..."
    gcloud artifacts repositories create "${REPOSITORY}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="VM Sheet Transformer images"
fi

if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" >/dev/null 2>&1; then
    echo "==> Creating runtime service account ${SERVICE_ACCOUNT_EMAIL}..."
    gcloud iam service-accounts create "${SERVICE_NAME}" \
        --display-name="VM Sheet Transformer runtime"
fi

echo "==> Building container with Cloud Build..."
gcloud builds submit \
    --tag "${IMAGE_URI}" \
    --region="${REGION}" \
    .

echo "==> Deploying to Cloud Run..."
AUTH_FLAG="--no-allow-unauthenticated"
[[ "${ALLOW_UNAUTH}" == "true" ]] && AUTH_FLAG="--allow-unauthenticated"

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_URI}" \
    --region="${REGION}" \
    --platform=managed \
    --service-account="${SERVICE_ACCOUNT_EMAIL}" \
    "${AUTH_FLAG}" \
    --port=8080 \
    --memory=1Gi \
    --cpu=1 \
    --concurrency=20 \
    --max-instances=5 \
    --timeout=300 \
    --set-env-vars="DEV_AUTH_BYPASS=true,SESSION_SECRET=playground-not-secret,ALLOWED_EMAIL_DOMAINS=devoteam.com,MAX_UPLOAD_MB=25,ENABLE_GCS_STORAGE=false,LOG_LEVEL=INFO"

URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format="value(status.url)")
echo
echo "==> Deployed."
echo "==> URL: ${URL}"
echo "==> Verify: curl ${URL}/health"
