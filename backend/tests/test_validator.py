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
    df = _base_df([{"name": "h1", "cpu": 4, "ram": 16, "disk": 100, "os": "Ubuntu 22.04 LTS"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


def test_missing_machinename_is_error():
    df = _base_df([{"name": "", "cpu": 4, "ram": 16, "disk": 100, "os": "Ubuntu 22.04 LTS"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "MachineName" for i in issues)


def test_missing_required_disk_is_error():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 16, "disk": "", "os": "Ubuntu 22.04 LTS"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "TotalDiskAllocatedGiB" for i in issues)


def test_missing_osname_is_error():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 16, "disk": 100, "os": ""}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "OsName" for i in issues)


def test_non_numeric_cpu_is_error():
    df = _base_df([{"name": "x", "cpu": "lots", "ram": 16, "disk": 100, "os": "Ubuntu 22.04 LTS"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "AllocatedProcessorCoreCount" for i in issues)


def test_invalid_isphysical_is_error():
    df = _base_df([
        {"name": "x", "cpu": 1, "ram": 1, "disk": 1, "os": "Ubuntu 22.04 LTS", "phys": "maybe"}
    ])
    mapping = {**_base_mapping(), "IsPhysical": "phys"}
    out = transform(df, mapping)
    out["IsPhysical"] = out["IsPhysical"].astype(object)
    out.loc[0, "IsPhysical"] = "maybe"
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "IsPhysical" for i in issues)


def test_duplicate_machineid_is_error():
    """Per spec: duplicate MachineId is an export-blocking ERROR."""
    df = _base_df([
        {"name": "a", "cpu": 1, "ram": 1, "disk": 1, "os": "Ubuntu 22.04 LTS"},
        {"name": "b", "cpu": 1, "ram": 1, "disk": 1, "os": "Ubuntu 22.04 LTS"},
    ])
    out = transform(df, _base_mapping())
    out["MachineId"] = ["DUP-001", "DUP-001"]  # force collision
    issues = validate(out)
    assert any(i.severity == "error" and i.target_column == "MachineId" for i in issues)


def test_duplicate_machinename_with_unique_machineid_is_warning_only():
    """Two rows with same name + distinct MachineId = warning, NOT error.
    Migration Center only requires MachineId uniqueness."""
    df = _base_df([
        {"name": "dup", "cpu": 1, "ram": 1, "disk": 1, "os": "Ubuntu 22.04 LTS"},
        {"name": "dup", "cpu": 1, "ram": 1, "disk": 1, "os": "Ubuntu 22.04 LTS"},
    ])
    out = transform(df, _base_mapping())
    issues = validate(out)
    errors = [i for i in issues if i.severity == "error"]
    name_issues = [i for i in issues if i.target_column == "MachineName"]
    assert errors == []
    assert any(i.severity == "warning" for i in name_issues)


def test_generic_os_value_is_warning_with_suggestions():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 16, "disk": 100, "os": "Windows"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    os_warnings = [i for i in issues if i.target_column == "OsName" and i.severity == "warning"]
    assert os_warnings
    assert "Windows Server" in os_warnings[0].suggested_fix


def test_generic_linux_is_warning():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 16, "disk": 100, "os": "Linux"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.target_column == "OsName" and i.severity == "warning" for i in issues)


def test_canonical_os_passes_without_warning():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 16, "disk": 100, "os": "Ubuntu 22.04 LTS"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert not any(i.target_column == "OsName" for i in issues)


def test_excessive_memory_is_warning():
    df = _base_df([{"name": "x", "cpu": 4, "ram": 8192, "disk": 100, "os": "Ubuntu 22.04 LTS"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "warning" and i.target_column == "MemoryGiB" for i in issues)


def test_excessive_cpu_is_warning():
    df = _base_df([{"name": "x", "cpu": 1024, "ram": 16, "disk": 100, "os": "Ubuntu 22.04 LTS"}])
    out = transform(df, _base_mapping())
    issues = validate(out)
    assert any(i.severity == "warning" and i.target_column == "AllocatedProcessorCoreCount" for i in issues)
