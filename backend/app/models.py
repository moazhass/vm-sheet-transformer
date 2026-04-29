"""Pydantic request/response models for the FastAPI surface."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MappingSuggestionModel(BaseModel):
    target_column: str
    source_column: str | None
    confidence: float
    rationale: str


class SheetInfoModel(BaseModel):
    name: str
    header_row_index: int
    columns: list[str]
    sample_rows: list[dict[str, Any]]
    row_count: int


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    sheets: list[SheetInfoModel]
    selected_sheet: str
    header_row_index: int
    source_columns: list[str]
    sample_rows: list[dict[str, Any]]
    row_count: int
    suggested_mapping: dict[str, MappingSuggestionModel]


class PreviewRequest(BaseModel):
    upload_id: str
    selected_sheet: str | None = None
    header_row_index: int = 0
    mapping: dict[str, str | None] = Field(default_factory=dict)
    defaults: dict[str, str] = Field(default_factory=dict)
    # If present, the server skips re-parse + re-transform and validates these
    # rows directly. Used by the inline-edit / Revalidate flow on the
    # Preview & Validate page. Internal fields prefixed with `_` are stripped
    # from the export.
    rows: list[dict[str, Any]] | None = None


class ValidationIssueModel(BaseModel):
    row: int
    target_column: str
    severity: Literal["error", "warning"]
    message: str
    suggested_fix: str = ""


class PreviewSummary(BaseModel):
    total_rows: int
    error_count: int
    warning_count: int
    distinct_machine_names: int


class PreviewResponse(BaseModel):
    rows: list[dict[str, Any]]
    issues: list[ValidationIssueModel]
    summary: PreviewSummary


class ExportRequest(PreviewRequest):
    format: Literal["csv", "xlsx"] = "csv"
