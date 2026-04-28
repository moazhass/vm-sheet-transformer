# VM Sheet Transformer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Internal Devoteam web app that transforms VM/server discovery sheets (CSV/XLSX/XLS) with arbitrary column layouts into the canonical `vmInfo_template.csv` schema using a deterministic, auditable mapping pipeline with a human-in-the-loop mapping review UI.

**Architecture:** FastAPI backend exposes upload/preview/export endpoints; transformation pipeline is decoupled (parser → mapper → transformer → validator → export) so each stage is independently testable. React+Vite+TS+Tailwind frontend walks user through Upload → Mapping → Preview → Export. Stateless processing in `/tmp` by default, optional GCS persistence. Google OAuth gates access via allowed email domains. No source data ever leaves the deployment (no external AI calls).

**Tech Stack:** Python 3.12, FastAPI, pandas, openpyxl, rapidfuzz · React 18, Vite, TypeScript, Tailwind · Docker → Cloud Run.

---

## File Structure & Responsibilities

### Backend
- `backend/app/config.py` — env-driven settings (Pydantic BaseSettings): allowed domains, max upload, GCS toggle, OAuth creds, session secret.
- `backend/app/models.py` — Pydantic request/response models (Mapping, PreviewRequest, ValidationIssue, etc.).
- `backend/app/parser.py` — file ingest. CSV (UTF-8 BOM safe), XLSX (multi-sheet), XLS. Header-row detection. Whitespace/character normalization.
- `backend/app/mapper.py` — synonym dictionaries + rapidfuzz scoring → suggested mapping with confidence. Pure function: `suggest_mapping(source_columns) -> dict[target_col, MappingSuggestion]`.
- `backend/app/transformer.py` — applies a confirmed mapping to source rows producing target-schema rows. Includes unit conversion, OS normalization, status normalization, MachineId generation, MachineTypeLabel inference, IP concatenation.
- `backend/app/validator.py` — runs required/format/duplicate/sanity rules; returns structured `ValidationIssue` list.
- `backend/app/export.py` — writes CSV/XLSX in exact target schema and column order; preserves empty optional fields as empty strings.
- `backend/app/auth.py` — Google OAuth flow, session middleware, email-domain allowlist guard, dev-mode bypass via env.
- `backend/app/storage.py` — pluggable storage: local /tmp (default) or GCS. Holds upload state by `upload_id`.
- `backend/app/main.py` — FastAPI app factory, routes (`/health`, `/api/upload`, `/api/mapping/preview`, `/api/export`, OAuth callback), CORS.

### Backend tests
- `backend/tests/test_parser.py` — header detection, multi-sheet, BOM.
- `backend/tests/test_mapper.py` — fuzzy matching, synonym hits, low-confidence behaviour.
- `backend/tests/test_transformer.py` — MB→GiB, TB→GiB, MachineId generation, type inference, OS/status normalization, IP concat, IsPhysical defaulting.
- `backend/tests/test_validator.py` — error/warning categorization, duplicates, sanity.
- `backend/tests/test_export.py` — exact column order, empty optional preservation.
- `backend/tests/fixtures/` — `sample_simple.csv`, `sample_messy.xlsx` (generated in conftest), `sample_units_mb.csv`.

### Frontend
- `frontend/src/types.ts` — TS contracts mirroring backend models.
- `frontend/src/api.ts` — fetch wrappers around the four endpoints.
- `frontend/src/App.tsx` — step state machine (upload→mapping→preview→export) with header/login.
- `frontend/src/components/UploadStep.tsx` — drag/drop + sheet picker.
- `frontend/src/components/MappingStep.tsx` — target-row × source-dropdown grid with confidence badge, defaults form.
- `frontend/src/components/PreviewStep.tsx` — transformed-row table.
- `frontend/src/components/ValidationPanel.tsx` — error/warning lists with filter.
- `frontend/src/components/ExportStep.tsx` — download triggers + summary.

### Deployment
- `Dockerfile` — multi-stage: build frontend with Node, install Python deps, copy `frontend/dist` into FastAPI static mount.
- `docker-compose.yml` — local dev convenience.
- `cloudbuild.yaml` — Cloud Build steps.
- `deploy-cloud-run.sh` — guarded apply script.
- `.env.example` — all knobs documented.

### Docs
- `README.md` — what/setup/deploy/auth/synonyms/limitations.
- `architecture.md` — Mermaid diagram + flows + security.

---

## Key Contracts

### `POST /api/upload` response
```json
{
  "upload_id": "uuid",
  "filename": "discovery.xlsx",
  "sheets": ["Sheet1", "Servers"],
  "selected_sheet": "Servers",
  "header_row_index": 2,
  "source_columns": ["Server Name", "vCPU", "..."],
  "sample_rows": [{"Server Name": "...", "...": "..."}],
  "row_count": 124,
  "suggested_mapping": {
    "MachineName": {"source_column": "Server Name", "confidence": 0.97, "rationale": "exact synonym"},
    "MachineId": {"source_column": null, "confidence": 0.0, "rationale": "generate"}
  }
}
```

### `POST /api/mapping/preview` request
```json
{
  "upload_id": "uuid",
  "selected_sheet": "Servers",
  "header_row_index": 2,
  "mapping": {"MachineName": "Server Name", "TotalDiskAllocatedGiB": "Disk (GB)"},
  "defaults": {"IsPhysical": "0", "OsName": "Windows"}
}
```

### `POST /api/export` request: same shape as preview + `format: "csv" | "xlsx"`. Returns binary file.

---

## Execution Order (in this session)

1. Backend tests written first for `mapper`, `transformer`, `validator`, `export`.
2. Implement those modules until tests pass.
3. Implement `parser`, `storage`, `auth`, `config`, `models`, `main` (FastAPI wiring — boilerplate exception per TDD skill).
4. Frontend scaffold + components.
5. Docker / Cloud Build / deploy script.
6. README + architecture.md.
7. Verification: `pytest` runs green; document Docker build / npm build status.

## Self-Review Checklist
- All 19 target columns implemented in transformer with exact synonyms? ✅ (mapper.py)
- MachineId generation uses `DISC-{seq:03d}-{MachineName}`? ✅
- Output CSV contains exactly the 19 template columns in template order? ✅ (export.py reads template header)
- Required-field validation covers: MachineName, MachineId-after-gen, TotalDiskAllocatedGiB, AllocatedProcessorCoreCount, MemoryGiB, OsName, IsPhysical? ✅
- Auth enforces ALLOWED_EMAIL_DOMAINS list? ✅
- Cloud Run port via `PORT` env? ✅
