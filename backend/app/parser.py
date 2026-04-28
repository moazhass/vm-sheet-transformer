"""Parse uploaded discovery sheets (CSV / XLSX / XLS).

Detects header row, drops fully empty rows, normalizes whitespace and weird
characters in headers and values. Keeps original sheet metadata for the
mapping UI.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

_INVISIBLE_CHARS = re.compile(r"[​-‏‪-‮﻿]")


def _clean_cell(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    if isinstance(v, str):
        s = unicodedata.normalize("NFKC", v)
        s = _INVISIBLE_CHARS.sub("", s)
        return s.strip()
    return v


def _row_meaningful_cells(row: pd.Series) -> int:
    count = 0
    for v in row:
        cleaned = _clean_cell(v)
        if isinstance(cleaned, str):
            if cleaned and not cleaned.isnumeric():
                count += 1
        elif cleaned not in (None, ""):
            count += 1
    return count


def detect_header_row(raw: pd.DataFrame, max_scan: int = 25) -> int:
    """Return the most likely header-row index in a no-header DataFrame.

    Heuristic: amongst the first `max_scan` rows, pick the one with the
    highest count of non-empty, non-numeric text cells. Tie-break by
    earliest row.
    """
    best_idx = 0
    best_score = -1
    limit = min(max_scan, len(raw))
    for i in range(limit):
        row = raw.iloc[i]
        score = _row_meaningful_cells(row)
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx


@dataclass
class SheetInfo:
    name: str
    header_row_index: int
    columns: list[str]
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0


@dataclass
class ParseResult:
    filename: str
    sheets: list[SheetInfo]


def _normalize_columns(cols: list[Any]) -> list[str]:
    out: list[str] = []
    seen: dict[str, int] = {}
    for c in cols:
        s = _clean_cell(c)
        s = str(s) if s != "" else ""
        if not s:
            s = "(unnamed)"
        if s in seen:
            seen[s] += 1
            s = f"{s} ({seen[s]})"
        else:
            seen[s] = 1
        out.append(s)
    return out


def _build_sheet(
    raw: pd.DataFrame, sheet_name: str, sample_size: int = 25
) -> SheetInfo:
    header_idx = detect_header_row(raw)
    headers = _normalize_columns(list(raw.iloc[header_idx]))
    body = raw.iloc[header_idx + 1 :].copy()
    body.columns = list(range(body.shape[1]))
    # Re-attach as named columns
    body = body.iloc[:, : len(headers)]
    body.columns = headers

    # Clean cells and drop fully empty rows
    body = body.map(_clean_cell)
    body = body.replace("", pd.NA).dropna(how="all").fillna("")

    sample_rows = body.head(sample_size).to_dict(orient="records")
    return SheetInfo(
        name=sheet_name,
        header_row_index=header_idx,
        columns=headers,
        sample_rows=sample_rows,
        row_count=int(body.shape[0]),
    )


def _read_csv_raw(path: Path) -> pd.DataFrame:
    """Read a CSV without using row 0 to infer column count.

    Discovery exports often have a 1-2 line preamble before the real header,
    which would otherwise cause pandas to truncate every wider row. We pre-scan
    with the csv module to find the widest row, then ask pandas to use that
    width via the ``names=`` parameter.
    """
    import csv

    max_cols = 0
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if len(row) > max_cols:
                max_cols = len(row)
    max_cols = max(max_cols, 1)
    return pd.read_csv(
        path,
        header=None,
        names=list(range(max_cols)),
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
        engine="python",
        on_bad_lines="skip",
    )


def parse_file(path: Path | str) -> ParseResult:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".csv":
        raw = _read_csv_raw(p)
        sheet = _build_sheet(raw, sheet_name="csv")
        return ParseResult(filename=p.name, sheets=[sheet])
    if suffix == ".xlsx":
        xls = pd.ExcelFile(p, engine="openpyxl")
    elif suffix == ".xls":
        xls = pd.ExcelFile(p, engine="xlrd")
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")

    sheets: list[SheetInfo] = []
    for name in xls.sheet_names:
        raw = pd.read_excel(xls, sheet_name=name, header=None, dtype=str)
        sheet = _build_sheet(raw, sheet_name=name)
        sheets.append(sheet)
    return ParseResult(filename=p.name, sheets=sheets)


def load_sheet_dataframe(
    path: Path | str, sheet_name: str | None, header_row_index: int
) -> pd.DataFrame:
    """Load a specific sheet's body using the chosen header row index."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".csv":
        raw = _read_csv_raw(p)
    elif suffix == ".xlsx":
        raw = pd.read_excel(p, sheet_name=sheet_name, header=None, dtype=str, engine="openpyxl")
    elif suffix == ".xls":
        raw = pd.read_excel(p, sheet_name=sheet_name, header=None, dtype=str, engine="xlrd")
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")

    headers = _normalize_columns(list(raw.iloc[header_row_index]))
    body = raw.iloc[header_row_index + 1 :].copy()
    body = body.iloc[:, : len(headers)]
    body.columns = headers
    body = body.map(_clean_cell)
    body = body.replace("", pd.NA).dropna(how="all").fillna("")
    return body
