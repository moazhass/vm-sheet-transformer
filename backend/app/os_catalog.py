"""GCE-aligned OS catalog with classification, canonicalization, and suggestions.

The canonical OS names match what Google Compute Engine surfaces in its
public image families and what Migration Center expects for OS detection.
All callers should treat this catalog as the single source of truth for
which OsName values are "good".

Three core concepts:
  * **canonical**: an exact entry in `GCE_OS_CATALOG` (e.g. "Ubuntu 22.04 LTS").
  * **generic**: a placeholder source value with no version info
    (e.g. "Windows", "Linux", "RHEL").
  * **classification** (`OsType`): WINDOWS / LINUX / UNKNOWN — internal-only,
    NEVER written to the export CSV. Used for UI filtering and the canonical
    `OsType(optional)` column gets the title-case form ("Windows" / "Linux").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

OsType = Literal["WINDOWS", "LINUX", "UNKNOWN"]


@dataclass(frozen=True)
class OsEntry:
    name: str             # canonical name written to CSV's OsName column
    type: OsType          # WINDOWS / LINUX / UNKNOWN
    publisher: str        # populates OsPublisher(optional)
    version: str          # populates OsVersion(optional)
    aliases: tuple[str, ...] = ()


# Order matters for the dropdown UI: most-recent / most-common first per family.
GCE_OS_CATALOG: tuple[OsEntry, ...] = (
    # ---- Windows Server ----
    OsEntry("Windows Server 2022 Datacenter", "WINDOWS", "Microsoft", "2022",
            ("windows server 2022", "windows server 2022 datacenter", "win 2022", "ws2022", "windows 2022")),
    OsEntry("Windows Server 2022 Datacenter Core", "WINDOWS", "Microsoft", "2022 Core",
            ("windows server 2022 core", "windows server 2022 datacenter core")),
    OsEntry("Windows Server 2019 Datacenter", "WINDOWS", "Microsoft", "2019",
            ("windows server 2019", "windows server 2019 datacenter", "windows server 2019 standard", "win 2019", "ws2019", "windows 2019")),
    OsEntry("Windows Server 2019 Datacenter Core", "WINDOWS", "Microsoft", "2019 Core",
            ("windows server 2019 core", "windows server 2019 datacenter core")),
    OsEntry("Windows Server 2016 Datacenter", "WINDOWS", "Microsoft", "2016",
            ("windows server 2016", "windows server 2016 datacenter", "windows server 2016 standard", "win 2016", "ws2016")),
    OsEntry("Windows Server 2016 Datacenter Core", "WINDOWS", "Microsoft", "2016 Core",
            ("windows server 2016 core", "windows server 2016 datacenter core")),
    OsEntry("Windows Server 2012 R2 Datacenter", "WINDOWS", "Microsoft", "2012 R2",
            ("windows server 2012 r2", "windows server 2012 r2 datacenter", "windows server 2012r2", "win 2012 r2", "ws2012r2")),
    OsEntry("Windows Server 2012 R2 Datacenter Core", "WINDOWS", "Microsoft", "2012 R2 Core",
            ("windows server 2012 r2 core", "windows server 2012 r2 datacenter core")),

    # ---- Ubuntu ----
    OsEntry("Ubuntu 24.04 LTS", "LINUX", "Canonical", "24.04",
            ("ubuntu 24.04", "ubuntu 24.04 lts", "ubuntu noble", "noble numbat")),
    OsEntry("Ubuntu 22.04 LTS", "LINUX", "Canonical", "22.04",
            ("ubuntu 22.04", "ubuntu 22.04 lts", "ubuntu jammy", "jammy jellyfish")),
    OsEntry("Ubuntu 20.04 LTS", "LINUX", "Canonical", "20.04",
            ("ubuntu 20.04", "ubuntu 20.04 lts", "ubuntu focal", "focal fossa")),
    OsEntry("Ubuntu Pro 24.04 LTS", "LINUX", "Canonical", "Pro 24.04",
            ("ubuntu pro 24.04", "ubuntu pro 24.04 lts")),
    OsEntry("Ubuntu Pro 22.04 LTS", "LINUX", "Canonical", "Pro 22.04",
            ("ubuntu pro 22.04", "ubuntu pro 22.04 lts")),

    # ---- Debian ----
    OsEntry("Debian 12", "LINUX", "Debian", "12",
            ("debian 12", "debian bookworm", "debian gnu/linux 12")),
    OsEntry("Debian 11", "LINUX", "Debian", "11",
            ("debian 11", "debian bullseye", "debian gnu/linux 11")),

    # ---- Red Hat Enterprise Linux ----
    OsEntry("Red Hat Enterprise Linux 9", "LINUX", "Red Hat", "9",
            ("rhel 9", "red hat 9", "redhat 9", "red hat enterprise linux 9", "rhel9")),
    OsEntry("Red Hat Enterprise Linux 8", "LINUX", "Red Hat", "8",
            ("rhel 8", "red hat 8", "redhat 8", "red hat enterprise linux 8", "rhel8")),
    OsEntry("Red Hat Enterprise Linux 7", "LINUX", "Red Hat", "7",
            ("rhel 7", "red hat 7", "redhat 7", "red hat enterprise linux 7", "rhel7")),

    # ---- Rocky Linux ----
    OsEntry("Rocky Linux 9", "LINUX", "Rocky Enterprise Software Foundation", "9",
            ("rocky 9", "rocky linux 9")),
    OsEntry("Rocky Linux 8", "LINUX", "Rocky Enterprise Software Foundation", "8",
            ("rocky 8", "rocky linux 8")),

    # ---- AlmaLinux ----
    OsEntry("AlmaLinux 9", "LINUX", "AlmaLinux OS Foundation", "9",
            ("alma 9", "almalinux 9", "alma linux 9")),
    OsEntry("AlmaLinux 8", "LINUX", "AlmaLinux OS Foundation", "8",
            ("alma 8", "almalinux 8", "alma linux 8")),

    # ---- SUSE ----
    OsEntry("SUSE Linux Enterprise Server 15", "LINUX", "SUSE", "15",
            ("sles 15", "suse 15", "suse linux enterprise server 15", "sles15")),

    # ---- Oracle Linux ----
    OsEntry("Oracle Linux 9", "LINUX", "Oracle", "9",
            ("oracle 9", "oracle linux 9", "ol9")),
    OsEntry("Oracle Linux 8", "LINUX", "Oracle", "8",
            ("oracle 8", "oracle linux 8", "ol8")),

    # ---- CentOS Stream ----
    OsEntry("CentOS Stream 9", "LINUX", "CentOS", "Stream 9",
            ("centos stream 9", "centos 9 stream", "cs9")),
)


# Set of canonical names for fast O(1) "is this exactly canonical?" checks.
CANONICAL_NAMES: frozenset[str] = frozenset(e.name for e in GCE_OS_CATALOG)


# Generic placeholders that should NEVER appear as OsName in an export.
# Lowercased for comparison; matches via exact-equals (case-insensitive trim).
GENERIC_OS_VALUES: frozenset[str] = frozenset({
    "", "windows", "linux", "unix",
    "ubuntu", "debian", "redhat", "red hat", "rhel", "centos",
    "rocky", "rocky linux", "alma", "almalinux", "suse", "sles",
    "oracle", "oracle linux",
    "unknown", "n/a", "na", "tbd", "other",
})


# When the source has only a generic value, suggest these canonical options
# in priority order (most recent / most common first).
OS_SUGGESTIONS: dict[str, tuple[str, ...]] = {
    "windows": (
        "Windows Server 2022 Datacenter",
        "Windows Server 2019 Datacenter",
        "Windows Server 2016 Datacenter",
        "Windows Server 2012 R2 Datacenter",
    ),
    "linux": (
        "Ubuntu 22.04 LTS",
        "Ubuntu 24.04 LTS",
        "Red Hat Enterprise Linux 9",
        "Debian 12",
    ),
    "ubuntu": (
        "Ubuntu 24.04 LTS",
        "Ubuntu 22.04 LTS",
        "Ubuntu 20.04 LTS",
    ),
    "debian": ("Debian 12", "Debian 11"),
    "redhat":  ("Red Hat Enterprise Linux 9", "Red Hat Enterprise Linux 8", "Red Hat Enterprise Linux 7"),
    "red hat": ("Red Hat Enterprise Linux 9", "Red Hat Enterprise Linux 8", "Red Hat Enterprise Linux 7"),
    "rhel":    ("Red Hat Enterprise Linux 9", "Red Hat Enterprise Linux 8", "Red Hat Enterprise Linux 7"),
    "centos":  ("CentOS Stream 9", "Rocky Linux 9", "AlmaLinux 9"),
    "rocky":   ("Rocky Linux 9", "Rocky Linux 8"),
    "alma":    ("AlmaLinux 9", "AlmaLinux 8"),
    "almalinux": ("AlmaLinux 9", "AlmaLinux 8"),
    "suse":    ("SUSE Linux Enterprise Server 15",),
    "oracle":  ("Oracle Linux 9", "Oracle Linux 8"),
    "unknown": (
        "Windows Server 2019 Datacenter",
        "Ubuntu 22.04 LTS",
        "Red Hat Enterprise Linux 8",
    ),
}


# Build alias lookup once at import time
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _e in GCE_OS_CATALOG:
    _ALIAS_TO_CANONICAL[_e.name.lower()] = _e.name
    for _a in _e.aliases:
        _ALIAS_TO_CANONICAL[_a.lower()] = _e.name


_LINUX_HINTS = re.compile(
    r"\b(linux|ubuntu|debian|rhel|red\s*hat|redhat|centos|fedora|suse|sles|"
    r"rocky|alma|almalinux|oracle\s*linux|amazon\s*linux|gentoo|arch)\b",
    re.IGNORECASE,
)
_WINDOWS_HINTS = re.compile(r"\b(windows|win\s*\d{2,4}|ws\d{4}|microsoft\s+windows)\b", re.IGNORECASE)


def _norm(s: str | None) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def is_canonical(os_name: str | None) -> bool:
    """True if `os_name` matches a GCE_OS_CATALOG entry exactly (case sensitive)."""
    return bool(os_name) and os_name in CANONICAL_NAMES


def is_generic(os_name: str | None) -> bool:
    """True if `os_name` is a placeholder with no version info ('Windows', 'Linux', etc.)."""
    n = _norm(os_name)
    return n in GENERIC_OS_VALUES and n != ""  # empty string handled separately as 'missing'


def classify_os_type(os_name: str | None) -> OsType:
    """Return WINDOWS, LINUX, or UNKNOWN for an OS name."""
    if not os_name:
        return "UNKNOWN"
    canonical = _ALIAS_TO_CANONICAL.get(_norm(os_name))
    if canonical:
        for e in GCE_OS_CATALOG:
            if e.name == canonical:
                return e.type
    if _WINDOWS_HINTS.search(os_name):
        return "WINDOWS"
    if _LINUX_HINTS.search(os_name):
        return "LINUX"
    return "UNKNOWN"


def canonicalize_os(raw: str | None) -> str | None:
    """Map a raw source OS string to a canonical catalog entry, or None if no match.

    Strategy:
      1. Exact case-insensitive match against canonical names + aliases.
      2. Substring match: every alias word appears in the source (e.g.
         "Windows Server 2019 Standard" → "Windows Server 2019 Datacenter").
    """
    if not raw:
        return None
    n = _norm(raw)
    hit = _ALIAS_TO_CANONICAL.get(n)
    if hit:
        return hit

    # Loose: try to match by the OS family + version number
    for e in GCE_OS_CATALOG:
        # Each alias is a phrase; if all of its words appear in the source, accept
        for alias in e.aliases + (e.name.lower(),):
            words = alias.split()
            if all(w in n for w in words):
                return e.name
    return None


def suggest_for(raw: str | None) -> tuple[str, ...]:
    """Return suggested canonical OS names for a generic / unrecognised value."""
    n = _norm(raw)
    if n in OS_SUGGESTIONS:
        return OS_SUGGESTIONS[n]
    # Try OS-family substrings
    for key, opts in OS_SUGGESTIONS.items():
        if key and key in n:
            return opts
    if not n:
        return OS_SUGGESTIONS["unknown"]
    return ()


def lookup(canonical_name: str) -> OsEntry | None:
    """Return the OsEntry matching a canonical name, or None."""
    for e in GCE_OS_CATALOG:
        if e.name == canonical_name:
            return e
    return None


def to_jsonable() -> dict:
    """Serialize the catalog for the /api/os-catalog endpoint."""
    return {
        "options": [
            {"name": e.name, "type": e.type, "publisher": e.publisher, "version": e.version}
            for e in GCE_OS_CATALOG
        ],
        "generic_values": sorted(GENERIC_OS_VALUES - {""}),
        "suggestions": {k: list(v) for k, v in OS_SUGGESTIONS.items()},
    }
