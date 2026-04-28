import pandas as pd

from app.transformer import transform
from app.validator import validate


def _base_df(rows):
    return pd.DataFrame(rows)


def _base_mapping():
    return {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }


def test_no_errors_for_clean_input():
    df = _base_df([{"name": "h1", "cpu": 4, "ram": 16, "disk": 100, "os": "Linux"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


def test_missing_machinename_is_error():
    df = _base_df([{"name": "", "cpu": 4, "ram": 16, "disk": 100, "os": "Linux"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "MachineName" for i in issues)


def test_missing_required_disk_is_error():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 16, "disk": "", "os": "Linux"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "TotalDiskAllocatedGiB" for i in issues)


def test_non_numeric_cpu_is_error():
    df = _base_df([{"name": "x", "cpu": "lots", "ram": 16, "disk": 100, "os": "Linux"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "AllocatedProcessorCoreCount" for i in issues)


def test_invalid_isphysical_is_error():
    df = _base_df([
        {"name": "x", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "phys": "maybe"}
    ])
    mapping = {**_base_mapping(), "IsPhysical": "phys"}
    out = transform(df, mapping)
    # Transformer treats unknown as 0; force-corruption (object dtype) to exercise validator path:
    out["IsPhysical"] = out["IsPhysical"].astype(object)
    out.loc[0, "IsPhysical"] = "maybe"
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "IsPhysical" for i in issues)


def test_duplicate_machinename_is_warning():
    df = _base_df([
        {"name": "dup", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
        {"name": "dup", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
    ])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "warning" and i.target_column == "MachineName" for i in issues)


def test_excessive_memory_is_warning():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 8192, "disk": 100, "os": "Linux"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "warning" and i.target_column == "MemoryGiB" for i in issues)


def test_excessive_cpu_is_warning():
    df = _base_df([{"name": "x", "cpu": 1024, "ram": 16, "disk": 100, "os": "Linux"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "warning" and i.target_column == "AllocatedProcessorCoreCount" for i in issues)
