"""HTTP-level tests for the new endpoints (rows-override + /api/os-catalog).

DEV_AUTH_BYPASS=true is set by tests/conftest.py so the auth dependency
returns a stub user.
"""

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_os_catalog_endpoint_shape():
    r = _client().get("/api/os-catalog")
    assert r.status_code == 200
    data = r.json()
    assert "options" in data
    assert "generic_values" in data
    assert "suggestions" in data
    names = {o["name"] for o in data["options"]}
    assert "Ubuntu 22.04 LTS" in names
    assert "Windows Server 2019 Datacenter" in names


def test_preview_with_rows_override_validates_only():
    """Send a row that already has a generic OsName; expect a warning issue
    without re-running the transformer."""
    rows = [{
        "MachineId": "DISC-001-X",
        "MachineName": "host1",
        "TotalDiskAllocatedGiB": 100,
        "AllocatedProcessorCoreCount": 4,
        "MemoryGiB": 16,
        "OsName": "Windows",          # generic → should produce a warning
        "IsPhysical": 0,
    }]
    r = _client().post(
        "/api/mapping/preview",
        json={"upload_id": "ignored-when-rows-present", "rows": rows},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["summary"]["total_rows"] == 1
    assert data["summary"]["error_count"] == 0
    assert data["summary"]["warning_count"] >= 1
    assert any(i["target_column"] == "OsName" and i["severity"] == "warning"
               for i in data["issues"])


def test_export_with_rows_override_emits_canonical_csv():
    rows = [{
        "MachineId": "DISC-001-X",
        "MachineName": "host1",
        "TotalDiskAllocatedGiB": 100,
        "AllocatedProcessorCoreCount": 4,
        "MemoryGiB": 16,
        "OsName": "Ubuntu 22.04 LTS",  # canonical → no warnings, no errors
        "IsPhysical": 0,
        "_source_os": "ubuntu 22",     # internal helper — must be stripped
        "_validation_status": "ok",
    }]
    r = _client().post(
        "/api/export",
        json={"upload_id": "ignored", "rows": rows, "format": "csv"},
    )
    assert r.status_code == 200, r.text
    text = r.content.decode("utf-8")
    header = text.splitlines()[0]
    assert "_source_os" not in header
    assert header.startswith("MachineId,MachineName,")
    assert header.endswith(",IsPhysical")


def test_export_blocked_when_rows_have_errors():
    rows = [{
        "MachineId": "",                 # missing → ERROR
        "MachineName": "",               # missing → ERROR
        "TotalDiskAllocatedGiB": "n/a",  # non-numeric → ERROR
        "AllocatedProcessorCoreCount": 4,
        "MemoryGiB": 16,
        "OsName": "",                    # missing → ERROR
        "IsPhysical": 0,
    }]
    r = _client().post(
        "/api/export",
        json={"upload_id": "ignored", "rows": rows, "format": "csv"},
    )
    assert r.status_code == 409
    body = r.json()
    assert "first_errors" in body["detail"]
