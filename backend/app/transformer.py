"""Apply a confirmed mapping to source rows producing target-schema rows.

Pure-function module: takes a pandas DataFrame of source rows plus a mapping
dict and optional defaults, returns a DataFrame in the canonical target
schema. No I/O. No global state.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

from app.mapper import TARGET_COLUMNS

_OS_NORMALIZATION = [
    (re.compile(r"\bwindows\b", re.I), "Windows"),
    (re.compile(r"\b(ubuntu|debian|red\s*hat|rhel|centos|oracle\s*linux|suse|sles|fedora|alma|rocky|amazon\s*linux|linux)\b", re.I), "Linux"),
]

_STATUS_MAP = {
    "powered on": "running", "poweron": "running", "power on": "running",
    "up": "running", "active": "running", "running": "running", "on": "running",
    "powered off": "stopped", "poweroff": "stopped", "power off": "stopped",
    "off": "stopped", "down": "stopped", "stopped": "stopped",
    "suspended": "suspended", "paused": "suspended", "suspend": "suspended",
}

# Per the spec these are "contains" checks. We use substring matching except
# for very short tokens (ad, fw, dc) which need a non-letter boundary to
# avoid spurious matches inside longer words.
_TOKEN_BOUNDARY = r"(?:^|[^a-z])"
_TOKEN_BOUNDARY_END = r"(?=$|[^a-z])"


def _bounded(*words: str) -> re.Pattern:
    body = "|".join(words)
    return re.compile(f"{_TOKEN_BOUNDARY}({body}){_TOKEN_BOUNDARY_END}", re.I)


_TYPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Most specific first so DB beats SQL fragment, and AD doesn't claim "DSCS".
    (_bounded("dc", "ad"), "AD"),
    (re.compile(r"domain[-_ ]?controller|active[-_ ]?directory", re.I), "AD"),
    (_bounded("fw"), "FW"),
    (re.compile(r"firewall|palo[-_ ]?alto|forti", re.I), "FW"),
    (re.compile(r"mgmt|management|jump|bastion", re.I), "MGMT"),
    (re.compile(r"sql|database|mssql|oracle|mysql|postgres|db", re.I), "DB"),
    (re.compile(r"web|iis|nginx|apache|httpd", re.I), "WEB"),
    (re.compile(r"app|api|service", re.I), "APP"),
    (_bounded("svc"), "APP"),
    (_bounded("dns"), "DNS"),
]

_PHYSICAL_TRUE = {"physical", "bare-metal", "baremetal", "bare metal", "1", "true", "yes"}
_PHYSICAL_FALSE = {"vm", "virtual", "virtual machine", "cloud", "instance", "0", "false", "no"}


def _str_or_empty(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() in {"nan", "none", "null"}:
        return ""
    return s


def _to_number(v: Any) -> float | None:
    s = _str_or_empty(v)
    if s == "":
        return None
    s = s.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _convert_size_to_gib(value: Any, source_header: str) -> Any:
    """Convert MB/TB → GiB if the source header hints the unit. Returns
    a numeric value when convertible, or the original string when not."""
    n = _to_number(value)
    if n is None:
        return _str_or_empty(value)
    h = source_header.lower()
    if "mb" in h and "gb" not in h and "gib" not in h:
        result = round(n / 1024.0, 4)
    elif "tb" in h:
        result = round(n * 1024.0, 4)
    else:
        result = n
    # Return integer when value is a whole number to avoid trailing ".0" in output
    if result == int(result):
        return int(result)
    return result


def _normalize_os_name(raw: str) -> str:
    s = _str_or_empty(raw)
    if not s:
        return ""
    for pattern, label in _OS_NORMALIZATION:
        if pattern.search(s):
            return label
    return s


def _extract_os_version(raw: str) -> str:
    s = _str_or_empty(raw)
    if not s:
        return ""
    m = re.search(r"\b(20\d{2}|1\d|2[0-4]\.\d{2}|\d+\.\d+(?:\.\d+)?)\b", s)
    return m.group(1) if m else ""


def _normalize_status(raw: str) -> str:
    s = _str_or_empty(raw).lower()
    if not s:
        return ""
    return _STATUS_MAP.get(s, s)


def _infer_type(name: str) -> str:
    if not name:
        return ""
    for pattern, label in _TYPE_PATTERNS:
        if pattern.search(name):
            return label
    return ""


def _normalize_physical(raw: Any) -> int:
    s = _str_or_empty(raw).lower()
    if s in _PHYSICAL_TRUE:
        return 1
    if s in _PHYSICAL_FALSE:
        return 0
    return 0


def _normalize_date(raw: Any) -> str:
    s = _str_or_empty(raw)
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s[:19], fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, errors="raise").date().isoformat()
    except (ValueError, TypeError):
        return s


def _generate_machine_id(seq: int, machine_name: str) -> str:
    safe = re.sub(r"\s+", "-", machine_name.strip())
    return f"DISC-{seq:03d}-{safe}".upper()


def transform(
    source_df: pd.DataFrame,
    mapping: dict[str, str],
    defaults: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Apply mapping to source_df, returning a DataFrame with target schema.

    Optional fields that are unmapped and have no default become empty strings
    so the export contains stable text rather than NaN.
    """
    defaults = defaults or {}
    out_rows: list[dict[str, Any]] = []

    name_col = mapping.get("MachineName")

    for idx, row in source_df.reset_index(drop=True).iterrows():
        out: dict[str, Any] = {col: "" for col in TARGET_COLUMNS}

        # MachineName
        machine_name = ""
        if name_col and name_col in row:
            machine_name = _str_or_empty(row[name_col])
        if not machine_name:
            machine_name = _str_or_empty(defaults.get("MachineName", ""))
        out["MachineName"] = machine_name

        # MachineId — use mapped value if present and non-empty, else generate
        id_col = mapping.get("MachineId")
        machine_id = _str_or_empty(row[id_col]) if id_col and id_col in row else ""
        if not machine_id:
            machine_id = _generate_machine_id(idx + 1, machine_name) if machine_name else ""
        out["MachineId"] = machine_id

        # IP fields
        for tgt in (
            "PrimaryIPAddress(optional)",
            "PrimaryMACAddress(optional)",
            "PublicIPAddress(optional)",
        ):
            src = mapping.get(tgt)
            out[tgt] = _str_or_empty(row[src]) if src and src in row else _str_or_empty(defaults.get(tgt, ""))

        # IP list — concatenate all known IPs if no explicit source provided
        ip_list_src = mapping.get("IpAddressListSemiColonDelimited(optional)")
        if ip_list_src and ip_list_src in row:
            out["IpAddressListSemiColonDelimited(optional)"] = _str_or_empty(row[ip_list_src])
        else:
            ips = [
                out["PrimaryIPAddress(optional)"],
                out["PublicIPAddress(optional)"],
            ]
            ips = [ip for ip in ips if ip]
            out["IpAddressListSemiColonDelimited(optional)"] = ";".join(ips)

        # Disk allocated
        src = mapping.get("TotalDiskAllocatedGiB")
        if src and src in row:
            out["TotalDiskAllocatedGiB"] = _convert_size_to_gib(row[src], src)
        else:
            out["TotalDiskAllocatedGiB"] = _str_or_empty(defaults.get("TotalDiskAllocatedGiB", ""))

        # Disk used (optional)
        src = mapping.get("TotalDiskUsedGiB")
        if src and src in row:
            out["TotalDiskUsedGiB"] = _convert_size_to_gib(row[src], src)
        else:
            out["TotalDiskUsedGiB"] = _str_or_empty(defaults.get("TotalDiskUsedGiB", ""))

        # Machine type label
        src = mapping.get("MachineTypeLabel(optional)")
        if src and src in row and _str_or_empty(row[src]):
            out["MachineTypeLabel(optional)"] = _str_or_empty(row[src])
        else:
            inferred = _infer_type(machine_name)
            out["MachineTypeLabel(optional)"] = inferred or _str_or_empty(
                defaults.get("MachineTypeLabel(optional)", "")
            )

        # CPU
        src = mapping.get("AllocatedProcessorCoreCount")
        if src and src in row:
            n = _to_number(row[src])
            out["AllocatedProcessorCoreCount"] = int(n) if n is not None and n == int(n) else (n if n is not None else _str_or_empty(row[src]))
        else:
            out["AllocatedProcessorCoreCount"] = _str_or_empty(defaults.get("AllocatedProcessorCoreCount", ""))

        # Memory
        src = mapping.get("MemoryGiB")
        if src and src in row:
            converted = _convert_size_to_gib(row[src], src)
            out["MemoryGiB"] = converted
        else:
            out["MemoryGiB"] = _str_or_empty(defaults.get("MemoryGiB", ""))

        # Hosting location
        src = mapping.get("HostingLocation(optional)")
        if src and src in row:
            out["HostingLocation(optional)"] = _str_or_empty(row[src])
        else:
            out["HostingLocation(optional)"] = _str_or_empty(defaults.get("HostingLocation(optional)", ""))

        # OS Type
        src = mapping.get("OsType(optional)")
        if src and src in row:
            out["OsType(optional)"] = _normalize_os_name(_str_or_empty(row[src]))
        else:
            out["OsType(optional)"] = _str_or_empty(defaults.get("OsType(optional)", ""))

        # OS Publisher
        src = mapping.get("OsPublisher(optional)")
        if src and src in row:
            out["OsPublisher(optional)"] = _str_or_empty(row[src])
        else:
            out["OsPublisher(optional)"] = _str_or_empty(defaults.get("OsPublisher(optional)", ""))

        # OS Name (required)
        src = mapping.get("OsName")
        raw_os = _str_or_empty(row[src]) if src and src in row else ""
        normalized = _normalize_os_name(raw_os)
        if not normalized:
            normalized = _str_or_empty(defaults.get("OsName", ""))
        out["OsName"] = normalized

        # OS Version
        src = mapping.get("OsVersion(optional)")
        if src and src in row and _str_or_empty(row[src]):
            out["OsVersion(optional)"] = _str_or_empty(row[src])
        elif raw_os:
            out["OsVersion(optional)"] = _extract_os_version(raw_os)
        else:
            out["OsVersion(optional)"] = _str_or_empty(defaults.get("OsVersion(optional)", ""))

        # Status
        src = mapping.get("MachineStatus(optional)")
        if src and src in row:
            out["MachineStatus(optional)"] = _normalize_status(_str_or_empty(row[src]))
        else:
            out["MachineStatus(optional)"] = _normalize_status(_str_or_empty(defaults.get("MachineStatus(optional)", "")))

        # Create date
        src = mapping.get("CreateDate(optional)")
        if src and src in row:
            out["CreateDate(optional)"] = _normalize_date(row[src])
        else:
            out["CreateDate(optional)"] = _normalize_date(defaults.get("CreateDate(optional)", ""))

        # IsPhysical (required, default 0)
        src = mapping.get("IsPhysical")
        if src and src in row:
            out["IsPhysical"] = _normalize_physical(row[src])
        else:
            default_val = _str_or_empty(defaults.get("IsPhysical", "0"))
            out["IsPhysical"] = _normalize_physical(default_val) if default_val else 0

        out_rows.append(out)

    df = pd.DataFrame(out_rows, columns=TARGET_COLUMNS)
    return df
