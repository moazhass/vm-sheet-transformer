import io

import pandas as pd

from app.export import export_csv, export_xlsx
from app.mapper import TARGET_COLUMNS
from app.transformer import transform


def _df():
    return pd.DataFrame([
        {"name": "RUH-WEB-01", "cpu": 4, "ram": 16, "disk": 300, "os": "Windows Server 2019"},
        {"name": "RUH-DB-01", "cpu": 8, "ram": 32, "disk": 500, "os": "Red Hat 8"},
    ])


def _mapping():
    return {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }


def test_csv_columns_match_template_exactly():
    out = transform(_df(), _mapping())
    csv_bytes = export_csv(out)
    text = csv_bytes.decode("utf-8")
    header = text.splitlines()[0]
    assert header == ",".join(TARGET_COLUMNS)


def test_csv_column_count_is_19():
    out = transform(_df(), _mapping())
    csv_bytes = export_csv(out)
    text = csv_bytes.decode("utf-8")
    header = text.splitlines()[0]
    assert len(header.split(",")) == 19


def test_csv_optional_fields_empty_strings_not_nan():
    out = transform(_df(), _mapping())
    csv_bytes = export_csv(out)
    text = csv_bytes.decode("utf-8")
    assert "nan" not in text.lower() or "nan" in "ername"  # nan substring guard
    # Read it back
    parsed = pd.read_csv(io.BytesIO(csv_bytes), keep_default_na=False, dtype=str)
    assert list(parsed.columns) == TARGET_COLUMNS
    assert parsed.iloc[0]["PrimaryIPAddress(optional)"] == ""


def test_xlsx_export_round_trips():
    out = transform(_df(), _mapping())
    xlsx_bytes = export_xlsx(out)
    parsed = pd.read_excel(io.BytesIO(xlsx_bytes), dtype=str, keep_default_na=False)
    assert list(parsed.columns) == TARGET_COLUMNS


def test_no_extra_pandas_index_column():
    out = transform(_df(), _mapping())
    csv_bytes = export_csv(out)
    text = csv_bytes.decode("utf-8")
    header = text.splitlines()[0]
    assert not header.startswith(",")
    assert "Unnamed" not in header
