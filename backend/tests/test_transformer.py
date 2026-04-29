import pandas as pd

from app.transformer import transform


def _df(rows):
    return pd.DataFrame(rows)


def test_machineid_generated_when_not_mapped():
    df = _df([
        {"Server Name": "RUH-WEB-01", "vCPU": 4, "RAM": 16, "Disk": 100, "OS": "Windows"},
        {"Server Name": "RUH-DB-01", "vCPU": 8, "RAM": 32, "Disk": 200, "OS": "Linux"},
    ])
    mapping = {
        "MachineName": "Server Name",
        "AllocatedProcessorCoreCount": "vCPU",
        "MemoryGiB": "RAM",
        "TotalDiskAllocatedGiB": "Disk",
        "OsName": "OS",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["MachineId"] == "DISC-001-RUH-WEB-01"
    assert out.iloc[1]["MachineId"] == "DISC-002-RUH-DB-01"


def test_machineid_passthrough_when_mapped():
    df = _df([{"ID": "EXISTING-1", "Server Name": "x", "vCPU": 1, "RAM": 1, "Disk": 1, "OS": "Linux"}])
    mapping = {
        "MachineId": "ID",
        "MachineName": "Server Name",
        "AllocatedProcessorCoreCount": "vCPU",
        "MemoryGiB": "RAM",
        "TotalDiskAllocatedGiB": "Disk",
        "OsName": "OS",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["MachineId"] == "EXISTING-1"


def test_memory_mb_to_gib_conversion_via_header_hint():
    df = _df([{"name": "h1", "Memory MB": 8192, "cpu": 2, "disk": 100, "os": "Linux"}])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "Memory MB",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert float(out.iloc[0]["MemoryGiB"]) == 8.0


def test_disk_tb_to_gib_conversion_via_header_hint():
    df = _df([{"name": "h1", "Disk (TB)": 1.5, "cpu": 2, "ram": 8, "os": "Linux"}])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "Disk (TB)",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert float(out.iloc[0]["TotalDiskAllocatedGiB"]) == 1536.0


def test_disk_mb_to_gib_conversion():
    df = _df([{"name": "h1", "Disk MB": 204800, "cpu": 2, "ram": 8, "os": "Linux"}])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "Disk MB",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert float(out.iloc[0]["TotalDiskAllocatedGiB"]) == 200.0


def test_os_canonicalization_preserves_version():
    """The transformer must preserve the actual OS version (not flatten to
    'Windows'/'Linux') so Migration Center can identify the workload."""
    df = _df([
        {"name": "a", "cpu": 1, "ram": 1, "disk": 1, "os": "Windows Server 2019"},
        {"name": "b", "cpu": 1, "ram": 1, "disk": 1, "os": "Ubuntu 22.04"},
        {"name": "c", "cpu": 1, "ram": 1, "disk": 1, "os": "Red Hat Enterprise Linux 8"},
        {"name": "d", "cpu": 1, "ram": 1, "disk": 1, "os": "CentOS Stream 9"},
        {"name": "e", "cpu": 1, "ram": 1, "disk": 1, "os": "Oracle Linux 9"},
    ])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["OsName"] == "Windows Server 2019 Datacenter"
    assert out.iloc[1]["OsName"] == "Ubuntu 22.04 LTS"
    assert out.iloc[2]["OsName"] == "Red Hat Enterprise Linux 8"
    assert out.iloc[3]["OsName"] == "CentOS Stream 9"
    assert out.iloc[4]["OsName"] == "Oracle Linux 9"


def test_os_type_publisher_version_derived_from_canonical():
    df = _df([{"name": "a", "cpu": 1, "ram": 1, "disk": 1, "os": "Ubuntu 22.04"}])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["OsType(optional)"] == "Linux"
    assert out.iloc[0]["OsPublisher(optional)"] == "Canonical"
    assert out.iloc[0]["OsVersion(optional)"] == "22.04"


def test_generic_os_value_preserved_for_validator_to_flag():
    """Generic placeholders like 'Windows' should NOT be silently mapped to a
    specific version. The transformer keeps them so validator warns the user."""
    df = _df([
        {"name": "a", "cpu": 1, "ram": 1, "disk": 1, "os": "Windows"},
        {"name": "b", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
    ])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["OsName"] == "Windows"
    assert out.iloc[1]["OsName"] == "Linux"


def test_status_normalization():
    df = _df([
        {"name": "a", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "st": "Powered On"},
        {"name": "b", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "st": "Powered Off"},
        {"name": "c", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "st": "Suspended"},
        {"name": "d", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "st": "active"},
    ])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
        "MachineStatus(optional)": "st",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["MachineStatus(optional)"] == "running"
    assert out.iloc[1]["MachineStatus(optional)"] == "stopped"
    assert out.iloc[2]["MachineStatus(optional)"] == "suspended"
    assert out.iloc[3]["MachineStatus(optional)"] == "running"


def test_machine_type_inferred_from_name():
    rows = [
        {"name": "RUH-WEB-01", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
        {"name": "RUH-APP-01", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
        {"name": "RUH-SQLDB-01", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
        {"name": "RUH-DC-01", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
        {"name": "RUH-FW-01", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
        {"name": "RUH-JUMPHOST", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
        {"name": "ZZZ-UNK-01", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"},
    ]
    df = _df(rows)
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }
    out = transform(df, mapping)
    expected = ["WEB", "APP", "DB", "AD", "FW", "MGMT", ""]
    for i, exp in enumerate(expected):
        assert out.iloc[i]["MachineTypeLabel(optional)"] == exp


def test_isphysical_default_zero_when_unknown():
    df = _df([{"name": "x", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"}])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["IsPhysical"] == 0


def test_isphysical_one_for_physical_value():
    df = _df([
        {"name": "a", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "phys": "Physical"},
        {"name": "b", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "phys": "Virtual"},
        {"name": "c", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "phys": "Bare-metal"},
        {"name": "d", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "phys": "VM"},
    ])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
        "IsPhysical": "phys",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["IsPhysical"] == 1
    assert out.iloc[1]["IsPhysical"] == 0
    assert out.iloc[2]["IsPhysical"] == 1
    assert out.iloc[3]["IsPhysical"] == 0


def test_defaults_apply_when_mapping_missing():
    df = _df([{"name": "x", "cpu": 1, "ram": 1, "disk": 1}])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
    }
    defaults = {"OsName": "Windows", "IsPhysical": "0", "MachineStatus(optional)": "running"}
    out = transform(df, mapping, defaults=defaults)
    assert out.iloc[0]["OsName"] == "Windows"
    assert out.iloc[0]["MachineStatus(optional)"] == "running"
    assert out.iloc[0]["IsPhysical"] == 0


def test_optional_fields_preserved_as_empty_strings():
    df = _df([{"name": "x", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux"}])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["PrimaryIPAddress(optional)"] == ""
    assert out.iloc[0]["PublicIPAddress(optional)"] == ""
    assert out.iloc[0]["CreateDate(optional)"] == ""


def test_create_date_iso_normalization():
    df = _df([
        {"name": "a", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "cd": "2023-04-01"},
        {"name": "b", "cpu": 1, "ram": 1, "disk": 1, "os": "Linux", "cd": "01/15/2024"},
    ])
    mapping = {
        "MachineName": "name",
        "AllocatedProcessorCoreCount": "cpu",
        "MemoryGiB": "ram",
        "TotalDiskAllocatedGiB": "disk",
        "OsName": "os",
        "CreateDate(optional)": "cd",
    }
    out = transform(df, mapping)
    assert out.iloc[0]["CreateDate(optional)"] == "2023-04-01"
    assert out.iloc[1]["CreateDate(optional)"] == "2024-01-15"
