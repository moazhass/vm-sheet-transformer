#!/usr/bin/env bash
# Deploy the VM Sheet Transformer to Cloud Run.
#
# Required env (export before running, or pass on the command line):
#   PROJECT_ID                Google Cloud project id
# Optional env (defaults shown):
#   REGION=me-central2
#   SERVICE_NAME=vm-sheet-transformer
#   REPOSITORY=vm-sheet-transformer
#   SERVICE_ACCOUNT_EMAIL=<service-name>@${PROJECT_ID}.iam.gserviceaccount.com
#   ALLOWED_EMAIL_DOMAINS=devoteam.com,devoteam.sa
#   MAX_UPLOAD_MB=25
#   ENABLE_GCS_STORAGE=false
#   GCS_BUCKET_NAME=
#
# OAuth secrets must already exist in Secret Manager:
#   vmt-session-secret, vmt-google-client-id, vmt-google-client-secret, vmt-oauth-redirect-url

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID env var is required}"
REGION="${REGION:-me-central2}"
SERVICE_NAME="${SERVICE_NAME:-vm-sheet-transformer}"
REPOSITORY="${REPOSITORY:-vm-sheet-transformer}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_EMAIL:-${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
ALLOWED_EMAIL_DOMAINS="${ALLOWED_EMAIL_DOMAINS:-devoteam.com,devoteam.sa}"
MAX_UPLOAD_MB="${MAX_UPLOAD_MB:-25}"
ENABLE_GCS_STORAGE="${ENABLE_GCS_STORAGE:-false}"
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "==> Project:        ${PROJECT_ID}"
echo "==> Region:         ${REGION}"
echo "==> Service:        ${SERVICE_NAME}"
echo "==> Image:          ${IMAGE_URI}"
echo "==> Service acct:   ${SERVICE_ACCOUNT_EMAIL}"
echo

gcloud config set project "${PROJECT_ID}" >/dev/null

echo "==> Enabling required APIs (idempotent)..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    --project="${PROJECT_ID}"

if ! gcloud artifacts repositories describe "${REPOSITORY}" --location="${REGION}" >/dev/null 2>&1; then
    echo "==> Creating Artifact Registry repo ${REPOSITORY}..."
    gcloud artifacts repositories create "${REPOSITORY}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="VM Sheet Transformer images"
fi

if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" >/dev/null 2>&1; then
    echo "==> Creating dedicated service account ${SERVICE_ACCOUNT_EMAIL}..."
    gcloud iam service-accounts create "${SERVICE_NAME}" \
        --display-name="VM Sheet Transformer runtime"
fi

echo "==> Granting Secret Manager accessor on the runtime service account..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None >/dev/null

if [[ "${ENABLE_GCS_STORAGE}" == "true" ]]; then
    if [[ -z "${GCS_BUCKET_NAME}" ]]; then
        echo "ERROR: GCS_BUCKET_NAME must be set when ENABLE_GCS_STORAGE=true"
        exit 1
    fi
    echo "==> Granting objectAdmin on gs://${GCS_BUCKET_NAME}..."
    gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET_NAME}" \
        --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
        --role="roles/storage.objectAdmin" >/dev/null
fi

echo "==> Building image with Cloud Build..."
gcloud builds submit \
    --tag "${IMAGE_URI}" \
    --region="${REGION}" \
    .

echo "==> Deploying to Cloud Run..."
ENV_VARS="ALLOWED_EMAIL_DOMAINS=${ALLOWED_EMAIL_DOMAINS},MAX_UPLOAD_MB=${MAX_UPLOAD_MB},ENABLE_GCS_STORAGE=${ENABLE_GCS_STORAGE},DEV_AUTH_BYPASS=false"
if [[ -n "${GCS_BUCKET_NAME}" ]]; then
    ENV_VARS="${ENV_VARS},GCS_BUCKET_NAME=${GCS_BUCKET_NAME}"
fi

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_URI}" \
    --region="${REGION}" \
    --platform=managed \
    --service-account="${SERVICE_ACCOUNT_EMAIL}" \
    --no-allow-unauthenticated \
    --port=8080 \
    --memory=1Gi \
    --cpu=1 \
    --concurrency=20 \
    --max-instances=5 \
    --timeout=300 \
    --set-env-vars="${ENV_VARS}" \
    --set-secrets="SESSION_SECRET=vmt-session-secret:latest,GOOGLE_CLIENT_ID=vmt-google-client-id:latest,GOOGLE_CLIENT_SECRET=vmt-google-client-secret:latest,OAUTH_REDIRECT_URL=vmt-oauth-redirect-url:latest"

URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format="value(status.url)")
echo
echo "==> Deployed."
echo "==> Service URL: ${URL}"
