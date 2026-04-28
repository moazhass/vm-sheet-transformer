"""Export transformed DataFrame to CSV/XLSX in the canonical target schema.

Always writes columns in TARGET_COLUMNS order. Empty optional cells are
written as empty strings (never NaN). No pandas index column. No extras.
"""

from __future__ import annotations

import io

import pandas as pd

from app.mapper import TARGET_COLUMNS


def _conform(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure every target column exists, in order; add missing as empty strings.
    out = pd.DataFrame({col: df[col] if col in df.columns else "" for col in TARGET_COLUMNS})
    # Replace any residual NaN with empty string for optional/text fields.
    out = out.fillna("")
    # Force everything to string-friendly representation; numeric values keep
    # their natural string form via pandas default to_csv.
    return out


def export_csv(df: pd.DataFrame) -> bytes:
    conformed = _conform(df)
    buf = io.StringIO()
    conformed.to_csv(buf, index=False, lineterminator="\n")
    return buf.getvalue().encode("utf-8")


def export_xlsx(df: pd.DataFrame) -> bytes:
    conformed = _conform(df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        conformed.to_excel(writer, index=False, sheet_name="vmInfo")
    return buf.getvalue()
