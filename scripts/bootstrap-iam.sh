#!/usr/bin/env bash
# Idempotent bootstrap for the CI/CD service accounts and IAM bindings.
# Run once per project. Re-running is safe: every step is idempotent.
#
# Required env (or override):
#   PROJECT=moaz-moazplayground
set -euo pipefail

PROJECT="${PROJECT:-moaz-moazplayground}"
CB_CICD="cb-cicd-sa@${PROJECT}.iam.gserviceaccount.com"
CB_PR="cb-pr-sa@${PROJECT}.iam.gserviceaccount.com"
CD_EXEC="cd-execution-sa@${PROJECT}.iam.gserviceaccount.com"
RT_PROD="vm-sheet-transformer@${PROJECT}.iam.gserviceaccount.com"
RT_STG="vm-sheet-transformer-staging@${PROJECT}.iam.gserviceaccount.com"

create_sa() {
  local sa="$1"
  local desc="$2"
  if gcloud iam service-accounts describe "${sa}@${PROJECT}.iam.gserviceaccount.com" --project="${PROJECT}" >/dev/null 2>&1; then
    echo "  ${sa} exists"
  else
    gcloud iam service-accounts create "${sa}" --project="${PROJECT}" --display-name="vmt: ${desc}"
  fi
}

bind() {
  local member="$1"
  local role="$2"
  gcloud projects add-iam-policy-binding "${PROJECT}" --member="${member}" --role="${role}" --condition=None >/dev/null
  echo "  bound ${role} -> ${member##*:}"
}

bind_sa_user() {
  local target_sa="$1"
  local member="$2"
  gcloud iam service-accounts add-iam-policy-binding "${target_sa}" --project="${PROJECT}" --member="${member}" --role=roles/iam.serviceAccountUser >/dev/null
  echo "  ${member##*:} can act-as ${target_sa%%@*}"
}

echo "==> Service accounts"
create_sa cb-cicd-sa "Cloud Build CI/CD trigger"
create_sa cb-pr-sa "Cloud Build PR trigger (read-only)"
create_sa cd-execution-sa "Cloud Deploy execution"
create_sa vm-sheet-transformer-staging "Cloud Run runtime - staging"
# vm-sheet-transformer (prod runtime) was created during the original deploy

echo "==> CB CI/CD SA roles"
for r in roles/cloudbuild.builds.builder roles/artifactregistry.writer roles/clouddeploy.releaser roles/logging.logWriter roles/storage.objectAdmin; do
  bind "serviceAccount:${CB_CICD}" "${r}"
done

echo "==> CB PR SA roles (limited)"
for r in roles/cloudbuild.builds.builder roles/logging.logWriter; do
  bind "serviceAccount:${CB_PR}" "${r}"
done

echo "==> CD execution SA roles"
for r in roles/clouddeploy.jobRunner roles/run.developer roles/logging.logWriter roles/storage.objectViewer; do
  bind "serviceAccount:${CD_EXEC}" "${r}"
done

echo "==> Cross-SA impersonation bindings"
bind_sa_user "${CD_EXEC}" "serviceAccount:${CB_CICD}"
bind_sa_user "${RT_PROD}" "serviceAccount:${CD_EXEC}"
bind_sa_user "${RT_STG}"  "serviceAccount:${CD_EXEC}"

echo "==> Done."
