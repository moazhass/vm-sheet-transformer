# Devoteam VM Sheet Transformer

Internal web application that converts heterogeneous VM/server discovery sheets
(CSV / XLSX / XLS) into the **canonical `vmInfo_template.csv` schema** used
downstream by the Devoteam migration tooling.

The transformation is **deterministic and auditable** — no source data is ever
sent to an external AI service. Every column mapping is suggested by a synonym
dictionary plus fuzzy matching, and every mapping is reviewable by the user
before export.

---

## What it does

1. **Upload** a CSV/XLSX/XLS discovery export.
2. The backend **detects sheets, finds the header row**, and **suggests a mapping**
   from each source column to the target template column with a confidence score.
3. **Mapping review UI** — the user can confirm, change, or override any mapping
   and set defaults for fields like `IsPhysical`, `OsName`, `MachineStatus`,
   `HostingLocation`.
4. **Preview & validate** — transformed rows are previewed; required-field /
   format / duplicate / sanity rules surface as errors and warnings.
5. **Export** — only allowed if there are no validation **errors**. Output is a
   CSV (or XLSX) that contains exactly the 19 template columns in the exact
   template order, with empty optional fields as empty strings.

The exported schema (always in this order):

```
MachineId, MachineName, PrimaryIPAddress(optional), PrimaryMACAddress(optional),
PublicIPAddress(optional), IpAddressListSemiColonDelimited(optional),
TotalDiskAllocatedGiB, TotalDiskUsedGiB, MachineTypeLabel(optional),
AllocatedProcessorCoreCount, MemoryGiB, HostingLocation(optional),
OsType(optional), OsPublisher(optional), OsName, OsVersion(optional),
MachineStatus(optional), CreateDate(optional), IsPhysical
```

Required fields: `MachineId`, `MachineName`, `TotalDiskAllocatedGiB`,
`AllocatedProcessorCoreCount`, `MemoryGiB`, `OsName`, `IsPhysical`.

---

## Repository layout

```
.
├── backend/                # FastAPI + transformation pipeline
│   ├── app/
│   │   ├── main.py         # FastAPI app & routes
│   │   ├── config.py       # Pydantic Settings (env-driven)
│   │   ├── auth.py         # Google OAuth + email-domain allowlist
│   │   ├── models.py       # API request/response models
│   │   ├── parser.py       # File ingest, sheet/header detection
│   │   ├── mapper.py       # Synonym + fuzzy column mapping
│   │   ├── transformer.py  # Apply mapping → target schema
│   │   ├── validator.py    # Required/format/sanity rules
│   │   ├── export.py       # CSV/XLSX writer (canonical schema)
│   │   └── storage.py      # /tmp + optional GCS storage
│   ├── tests/              # pytest unit tests (36 tests)
│   └── requirements.txt
├── frontend/               # Vite + React + TS + Tailwind SPA
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── components/{Upload,Mapping,Preview,Validation,Export}*.tsx
│   ├── package.json
│   └── vite.config.ts
├── templates/
│   └── vmInfo_template.csv # Canonical target schema (header-only reference)
├── Dockerfile              # Multi-stage: builds SPA, packs Python runtime
├── docker-compose.yml      # Local one-command run
├── cloudbuild.yaml         # Cloud Build pipeline → Cloud Run
├── deploy-cloud-run.sh     # Idempotent deploy from a workstation
├── .env.example
├── architecture.md
└── README.md
```

---

## Local setup

### 1. Run with Docker (one command)

```bash
docker compose up --build
# open http://localhost:8080
```

`docker-compose.yml` sets `DEV_AUTH_BYPASS=true` so you don't need to wire OAuth
to test locally. It serves the SPA from the same port as the API.

### 2. Run backend and frontend separately (development)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
DEV_AUTH_BYPASS=true SESSION_SECRET=dev uvicorn app.main:app --reload --port 8080
```

Frontend (separate terminal):

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 — proxies /api and /auth to :8080
```

### 3. Run the backend tests

```bash
cd backend
pip install -r requirements.txt
python -m pytest -v
# 36 passed in ~2s
```

---

## Environment variables

See [`.env.example`](.env.example) for the full list.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8080` | Cloud Run injects this; the app must listen on it. |
| `ALLOWED_EMAIL_DOMAINS` | `devoteam.com,devoteam.sa` | Comma-separated Google domain allowlist. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | — | OAuth credentials. |
| `OAUTH_REDIRECT_URL` | — | Public callback URL (e.g. `https://…/auth/callback`). |
| `SESSION_SECRET` | `change-me` | Cookie signing key. **Rotate.** |
| `DEV_AUTH_BYPASS` | `false` | Skips OAuth entirely. **Local dev only.** |
| `MAX_UPLOAD_MB` | `25` | Hard cap per upload. |
| `UPLOAD_RETENTION_MINUTES` | `60` | Background eviction window for `/tmp` uploads. |
| `ENABLE_GCS_STORAGE` | `false` | Mirror uploads to a GCS bucket. |
| `GCS_BUCKET_NAME` | — | Required if GCS is enabled. |
| `FRONTEND_DIST_DIR` | `frontend/dist` | Where the FastAPI process serves the SPA from. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

---

## Deploy to Cloud Run

### Option A — `deploy-cloud-run.sh` (workstation)

```bash
export PROJECT_ID=devoteam-vmt-prod
# Optional overrides:
# export REGION=me-central2
# export ALLOWED_EMAIL_DOMAINS=devoteam.com,devoteam.sa
# export ENABLE_GCS_STORAGE=true GCS_BUCKET_NAME=devoteam-vmt-uploads

./deploy-cloud-run.sh
```

The script will:

1. Enable required APIs (`run`, `artifactregistry`, `cloudbuild`, `secretmanager`).
2. Create the Artifact Registry repo if needed.
3. Create a dedicated runtime service account if needed and grant
   `roles/secretmanager.secretAccessor`.
4. (If GCS enabled) grant `roles/storage.objectAdmin` on the chosen bucket.
5. Build the container with Cloud Build and push to Artifact Registry.
6. Deploy to Cloud Run with `--no-allow-unauthenticated`.
7. Print the service URL.

Before first deploy, create the four Secret Manager secrets the service expects:

```bash
echo -n "$(openssl rand -hex 32)" | gcloud secrets create vmt-session-secret --data-file=-
echo -n "$GOOGLE_CLIENT_ID"        | gcloud secrets create vmt-google-client-id --data-file=-
echo -n "$GOOGLE_CLIENT_SECRET"    | gcloud secrets create vmt-google-client-secret --data-file=-
echo -n "https://<service-url>/auth/callback" | gcloud secrets create vmt-oauth-redirect-url --data-file=-
```

### Option B — `cloudbuild.yaml` (CI trigger)

Wire a Cloud Build trigger pointing at this repo with `cloudbuild.yaml`. It
builds, pushes, and deploys in a single pipeline.

---

## How authentication works

- The frontend hits `/api/me` on load. If the response is `401`, the user is
  redirected to `/auth/login`, which initiates the Google OAuth flow.
- `auth.py` allows the login only if the verified email's domain is in
  `ALLOWED_EMAIL_DOMAINS` (comma-separated).
- The user object (email, name, picture) is stored in a signed session cookie
  (`SessionMiddleware`) and read on every protected request.
- `DEV_AUTH_BYPASS=true` short-circuits the entire flow with a fake user — for
  local development only.

For enterprise deployments, consider fronting the service with **Identity-Aware
Proxy (IAP)** instead — see [architecture.md](architecture.md) for notes.

---

## How to add new mapping synonyms

Edit `backend/app/mapper.py` and append to the relevant `SYNONYMS` entry. Each
entry is a list of lower-case phrases compared (case-insensitively, punctuation
ignored) against incoming source headers. After editing, add a regression test
in `backend/tests/test_mapper.py` that asserts the new synonym maps to the
expected target column, then run `pytest`.

```python
SYNONYMS["MemoryGiB"] = [
    "memory", "ram", "memory gb", "ram gb", "memory mb", "ram mb",
    "ram (gb)", "memory (gb)", "ram (mb)", "memory (mb)",
    "physical memory",   # ← new synonym
]
```

To add a new **target column** you would also need to update
`TARGET_COLUMNS`, the transformer logic for that field, and the
`templates/vmInfo_template.csv` header. The export, validator, mapper, and
frontend pick the schema up automatically once `TARGET_COLUMNS` is updated.

---

## Security model (summary — see architecture.md)

- Access gated by Google OAuth + email-domain allowlist.
- File-extension and size validation on every upload (`MAX_UPLOAD_MB`).
- Uploaded files **never executed**, only parsed by pandas / openpyxl / xlrd.
- Default storage is **stateless**: files live in `/tmp` and are evicted after
  `UPLOAD_RETENTION_MINUTES` minutes.
- Optional GCS persistence via `ENABLE_GCS_STORAGE=true` + `GCS_BUCKET_NAME`.
  **Recommended bucket lifecycle policy:** delete objects older than 24 hours.
  Sample command:
  ```bash
  cat <<EOF > lifecycle.json
  {"lifecycle":{"rule":[{"action":{"type":"Delete"},"condition":{"age":1}}]}}
  EOF
  gcloud storage buckets update gs://${GCS_BUCKET_NAME} --lifecycle-file=lifecycle.json
  ```
- Logs include only metadata (upload_id, row counts, error counts, user email).
  **No row-level data is logged.**

---

## Known limitations

- **Single-user transformation context**: the mapping/preview state is per
  upload_id stored in the live process. Cloud Run instances may scale to zero,
  in which case the upload_id will become unknown unless `ENABLE_GCS_STORAGE`
  is enabled. Set `--max-instances=1` if you need ephemeral consistency without
  GCS, or enable GCS for resilience.
- **XLSX cell formulas**: only computed values are read (openpyxl
  `data_only=False` would return the formula text — we always read the value
  cell). If the source workbook has uncalculated formulas, open and save it in
  Excel/LibreOffice first.
- **Header-row detection** picks the row with the most non-numeric text cells
  in the first 25 rows. Files with multiple banded "section" headers may need
  the user to override the header row index in a future UI iteration (the API
  already accepts `header_row_index`).
- **OAuth callback URL** must be reachable publicly (configure in the Google
  Cloud Console OAuth client). Cloud Run gives you a stable `*.run.app` URL.
- **Date parsing** is best-effort; uncommon locale formats fall through to the
  raw value. Add formats to `_normalize_date` in `transformer.py` as needed.

---

## Future enhancements (not implemented)

- Reusable mapping profiles per customer/project (saved to GCS or Firestore).
- BigQuery direct export of the canonical table.
- Audit-log table (Cloud Logging sink → BigQuery).
- Admin screen for synonym management.
- Cloud Storage lifecycle automation as part of the deploy script.
- IAP-based auth with VPC-SC for stricter enterprise deployments.
