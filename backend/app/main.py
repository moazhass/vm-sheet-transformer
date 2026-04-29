"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    install_session_middleware,
    login_redirect,
    logout,
    oauth_callback,
    require_user,
)
from app.config import get_settings
from app.export import export_csv, export_xlsx
from app.mapper import REQUIRED_COLUMNS, TARGET_COLUMNS, suggest_mapping, to_dict
from app.os_catalog import to_jsonable as os_catalog_jsonable
from app.models import (
    ExportRequest,
    MappingSuggestionModel,
    PreviewRequest,
    PreviewResponse,
    PreviewSummary,
    SheetInfoModel,
    UploadResponse,
    ValidationIssueModel,
)
from app.parser import load_sheet_dataframe, parse_file
from app.storage import get_store
from app.transformer import transform
from app.validator import validate

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("vmt")

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Devoteam VM Sheet Transformer",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    install_session_middleware(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "vm-sheet-transformer",
            "version": app.version,
            "auth_bypass": settings.dev_auth_bypass,
        }

    @app.get("/api/me")
    async def me(user: dict = Depends(require_user)) -> dict:
        return user

    @app.get("/auth/login", name="auth_login")
    async def auth_login(request: Request):
        return await login_redirect(request)

    @app.get("/auth/callback", name="auth_callback")
    async def auth_callback(request: Request):
        return await oauth_callback(request)

    @app.get("/auth/logout", name="auth_logout")
    async def auth_logout(request: Request):
        return logout(request)

    @app.get("/api/template-columns")
    async def template_columns(user: dict = Depends(require_user)) -> dict:
        return {
            "target_columns": TARGET_COLUMNS,
            "required_columns": sorted(REQUIRED_COLUMNS),
        }

    @app.get("/api/os-catalog")
    async def os_catalog(user: dict = Depends(require_user)) -> dict:
        return os_catalog_jsonable()

    @app.post("/api/upload", response_model=UploadResponse)
    async def upload(
        request: Request,
        file: UploadFile = File(...),
        user: dict = Depends(require_user),
    ) -> UploadResponse:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported extension '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )

        max_bytes = settings.max_upload_mb * 1024 * 1024
        data = await file.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max allowed: {settings.max_upload_mb} MB",
            )

        store = get_store()
        record = store.save(file.filename or "upload.csv", data)
        store.evict_expired()

        try:
            parsed = parse_file(record.local_path)
        except Exception as exc:
            logger.exception("parse failed for upload_id=%s", record.upload_id)
            raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

        first_sheet = parsed.sheets[0]
        suggestions = suggest_mapping(first_sheet.columns)
        suggested_mapping = {k: MappingSuggestionModel(**to_dict(v)) for k, v in suggestions.items()}

        logger.info(
            "upload upload_id=%s file=%s sheets=%s rows=%s user=%s",
            record.upload_id,
            file.filename,
            [s.name for s in parsed.sheets],
            first_sheet.row_count,
            user.get("email"),
        )

        return UploadResponse(
            upload_id=record.upload_id,
            filename=file.filename or "upload.csv",
            sheets=[
                SheetInfoModel(
                    name=s.name,
                    header_row_index=s.header_row_index,
                    columns=s.columns,
                    sample_rows=s.sample_rows,
                    row_count=s.row_count,
                )
                for s in parsed.sheets
            ],
            selected_sheet=first_sheet.name,
            header_row_index=first_sheet.header_row_index,
            source_columns=first_sheet.columns,
            sample_rows=first_sheet.sample_rows,
            row_count=first_sheet.row_count,
            suggested_mapping=suggested_mapping,
        )

    def _load_for_request(req: PreviewRequest):
        # Inline-edit / Revalidate path: trust the rows the client sends.
        # Helper fields prefixed with `_` are stripped here so they never
        # leak into validation or export.
        if req.rows is not None:
            import pandas as pd
            from app.os_catalog import canonicalize_os, classify_os_type, lookup
            cleaned = [
                {k: v for k, v in row.items() if not k.startswith("_")}
                for row in req.rows
            ]
            out = pd.DataFrame(cleaned)
            for col in TARGET_COLUMNS:
                if col not in out.columns:
                    out[col] = ""
            out = out[TARGET_COLUMNS].fillna("")

            # Re-derive OsType/OsPublisher/OsVersion from the (possibly edited)
            # OsName so the export always carries Migration-Center-friendly
            # metadata. Existing non-empty user values are preserved.
            for idx, row in out.iterrows():
                os_name = str(row.get("OsName", "") or "").strip()
                if not os_name:
                    continue
                canonical = canonicalize_os(os_name)
                entry = lookup(canonical) if canonical else None
                if not str(row.get("OsType(optional)", "") or "").strip():
                    t = classify_os_type(os_name)
                    out.at[idx, "OsType(optional)"] = (
                        "Windows" if t == "WINDOWS" else "Linux" if t == "LINUX" else ""
                    )
                if entry:
                    if not str(row.get("OsPublisher(optional)", "") or "").strip():
                        out.at[idx, "OsPublisher(optional)"] = entry.publisher
                    if not str(row.get("OsVersion(optional)", "") or "").strip():
                        out.at[idx, "OsVersion(optional)"] = entry.version

            return None, None, out

        # Original path: parse → transform from the upload.
        record = get_store().get(req.upload_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Upload not found or expired")
        df = load_sheet_dataframe(record.local_path, req.selected_sheet, req.header_row_index)
        cleaned_mapping = {k: v for k, v in req.mapping.items() if v}
        out = transform(df, cleaned_mapping, defaults=req.defaults)
        return record, df, out

    @app.post("/api/mapping/preview", response_model=PreviewResponse)
    async def preview(req: PreviewRequest, user: dict = Depends(require_user)) -> PreviewResponse:
        _, _, out = _load_for_request(req)
        issues = validate(out)
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        sample = out.head(50).to_dict(orient="records")
        logger.info(
            "preview upload_id=%s rows=%d errors=%d warnings=%d user=%s",
            req.upload_id, len(out), len(errors), len(warnings), user.get("email"),
        )
        return PreviewResponse(
            rows=sample,
            issues=[ValidationIssueModel(**i.to_dict()) for i in issues],
            summary=PreviewSummary(
                total_rows=len(out),
                error_count=len(errors),
                warning_count=len(warnings),
                distinct_machine_names=int(out["MachineName"].astype(str).nunique()),
            ),
        )

    @app.post("/api/export")
    async def export(req: ExportRequest, user: dict = Depends(require_user)):
        _, _, out = _load_for_request(req)
        issues = validate(out)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Cannot export — fix validation errors first.",
                    "error_count": len(errors),
                    "first_errors": [i.to_dict() for i in errors[:10]],
                },
            )
        if req.format == "xlsx":
            data = export_xlsx(out)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext = "xlsx"
        else:
            data = export_csv(out)
            media = "text/csv"
            ext = "csv"

        logger.info(
            "export upload_id=%s format=%s rows=%d user=%s",
            req.upload_id, req.format, len(out), user.get("email"),
        )
        filename = f"vmInfo_export.{ext}"
        return StreamingResponse(
            BytesIO(data),
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Static frontend (when present)
    dist = Path(settings.frontend_dist_dir)
    if dist.exists() and dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")
    else:
        @app.get("/")
        async def root_placeholder() -> JSONResponse:
            return JSONResponse(
                {
                    "service": "vm-sheet-transformer",
                    "frontend": "not built — see README to build the SPA",
                    "api_docs": "/api/docs",
                }
            )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
