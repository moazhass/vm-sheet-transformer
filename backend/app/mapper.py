"""Deterministic source-to-target column mapper.

Suggests a mapping from arbitrary source column names to the fixed target
schema using a synonym dictionary plus rapidfuzz token-set ratio scoring.
No external services. No LLM calls. Fully reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from rapidfuzz import fuzz, process

# Exact column order required for the export. Do not reorder.
TARGET_COLUMNS: list[str] = [
    "MachineId",
    "MachineName",
    "PrimaryIPAddress(optional)",
    "PrimaryMACAddress(optional)",
    "PublicIPAddress(optional)",
    "IpAddressListSemiColonDelimited(optional)",
    "TotalDiskAllocatedGiB",
    "TotalDiskUsedGiB",
    "MachineTypeLabel(optional)",
    "AllocatedProcessorCoreCount",
    "MemoryGiB",
    "HostingLocation(optional)",
    "OsType(optional)",
    "OsPublisher(optional)",
    "OsName",
    "OsVersion(optional)",
    "MachineStatus(optional)",
    "CreateDate(optional)",
    "IsPhysical",
]

REQUIRED_COLUMNS: set[str] = {
    "MachineId",
    "MachineName",
    "TotalDiskAllocatedGiB",
    "AllocatedProcessorCoreCount",
    "MemoryGiB",
    "OsName",
    "IsPhysical",
}

# Synonyms per target column. Keys are the canonical target names.
# Match logic is case-insensitive and punctuation-tolerant.
SYNONYMS: dict[str, list[str]] = {
    "MachineId": [
        "machine id", "vm id", "server id", "asset id", "instance id", "id",
    ],
    "MachineName": [
        "machine name", "vm name", "hostname", "host name", "server name", "server",
        "name", "computer name", "dns name", "instance name", "asset name",
    ],
    "PrimaryIPAddress(optional)": [
        "primary ip", "private ip", "ip address", "ip", "management ip",
        "internal ip", "nic ip",
    ],
    "PrimaryMACAddress(optional)": [
        "mac", "mac address", "primary mac", "physical address",
    ],
    "PublicIPAddress(optional)": [
        "public ip", "external ip", "internet ip", "nat ip",
    ],
    "IpAddressListSemiColonDelimited(optional)": [
        "ip list", "all ips", "ip addresses", "ipaddresslist", "secondary ips",
    ],
    "TotalDiskAllocatedGiB": [
        "disk", "total disk", "allocated disk", "provisioned disk", "storage",
        "disk gb", "storage gb", "capacity", "capacity gb", "provisioned storage",
        "disk (gb)", "storage (gb)", "disk mb", "disk tb",
    ],
    "TotalDiskUsedGiB": [
        "used disk", "consumed disk", "used storage", "disk used", "storage used",
    ],
    "MachineTypeLabel(optional)": [
        "role", "type", "workload", "application tier", "server role", "machine type",
    ],
    "AllocatedProcessorCoreCount": [
        "cpu", "cpus", "vcpu", "vcpus", "cores", "processor cores", "allocated cpu",
        "core count", "processor count",
    ],
    "MemoryGiB": [
        "memory", "ram", "memory gb", "ram gb", "memory mb", "ram mb",
        "ram (gb)", "memory (gb)", "ram (mb)", "memory (mb)",
    ],
    "HostingLocation(optional)": [
        "location", "site", "datacenter", "data center", "hosting location",
        "zone", "environment", "tier", "network zone",
    ],
    "OsType(optional)": [
        "os type", "operating system type", "platform",
    ],
    "OsPublisher(optional)": [
        "os publisher", "publisher", "vendor", "os vendor",
    ],
    "OsName": [
        "os", "os name", "operating system", "guest os", "guest operating system",
    ],
    "OsVersion(optional)": [
        "os version", "version", "build", "operating system version",
    ],
    "MachineStatus(optional)": [
        "status", "power state", "state", "machine status",
    ],
    "CreateDate(optional)": [
        "created", "create date", "creation date", "provision date", "deployment date",
    ],
    "IsPhysical": [
        "physical", "is physical", "machine type", "asset type", "virtualization type",
    ],
}


@dataclass
class MappingSuggestion:
    target_column: str
    source_column: str | None
    confidence: float
    rationale: str


_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize(s: str) -> str:
    return _NORMALIZE_RE.sub(" ", s.lower()).strip()


def _best_match_for_target(
    target: str, candidates: list[str], used: set[str]
) -> tuple[str | None, float, str]:
    syns = SYNONYMS.get(target, [])
    norm_candidates = {c: _normalize(c) for c in candidates if c not in used}
    if not norm_candidates:
        return (None, 0.0, "no source columns available")

    best_col: str | None = None
    best_score = 0.0
    best_reason = ""

    for syn in syns:
        norm_syn = _normalize(syn)
        # Exact normalized match wins immediately
        for col, norm_col in norm_candidates.items():
            if norm_col == norm_syn:
                return (col, 1.0, f"exact match for synonym '{syn}'")

        # Otherwise compute fuzzy score per candidate
        scored = process.extract(
            norm_syn,
            list(norm_candidates.values()),
            scorer=fuzz.WRatio,
            limit=1,
        )
        if scored:
            matched_value, score, _ = scored[0]
            score_ratio = score / 100.0
            if score_ratio > best_score:
                col = next(c for c, n in norm_candidates.items() if n == matched_value)
                best_col = col
                best_score = score_ratio
                best_reason = f"fuzzy match against synonym '{syn}' ({score:.0f}%)"

    if best_col is None or best_score < 0.70:
        return (None, 0.0, "no confident match")
    return (best_col, round(best_score, 3), best_reason)


def _exact_match_for_target(
    target: str, candidates: list[str], used: set[str]
) -> tuple[str | None, str]:
    """Return (col, reason) only if a synonym matches a candidate exactly
    (after normalization). Otherwise (None, '')."""
    syns = SYNONYMS.get(target, [])
    norm_syns = {_normalize(s) for s in syns}
    for col in candidates:
        if col in used:
            continue
        if _normalize(col) in norm_syns:
            return (col, f"exact match for synonym '{col}'")
    return (None, "")


def suggest_mapping(source_columns: Iterable[str]) -> dict[str, MappingSuggestion]:
    """Return a MappingSuggestion for every target column.

    Two-pass strategy:
      1. Every target column gets first refusal on its EXACT-match synonyms,
         iterated in TARGET_COLUMNS order. This prevents short synonyms like
         "ip" from stealing a column ("Public IP") that another target would
         match exactly.
      2. Remaining targets fall back to fuzzy matching, required fields first.
    """
    cols = [c for c in source_columns if c is not None and str(c).strip() != ""]
    suggestions: dict[str, MappingSuggestion] = {}
    used: set[str] = set()

    # ---- Pass 1: exact synonym matches in target order ----
    for target in TARGET_COLUMNS:
        if target == "MachineId":
            continue  # handled below
        col, reason = _exact_match_for_target(target, cols, used)
        if col is not None:
            suggestions[target] = MappingSuggestion(target, col, 1.0, reason)
            used.add(col)

    # ---- MachineId resolution (exact then fuzzy) ----
    col, score, reason = _best_match_for_target("MachineId", cols, used)
    if col and score >= 0.85:
        suggestions["MachineId"] = MappingSuggestion("MachineId", col, score, reason)
        used.add(col)
    else:
        suggestions["MachineId"] = MappingSuggestion(
            "MachineId", None, 0.0,
            "generate as DISC-{seq:03d}-{MachineName}",
        )

    # ---- Pass 2: fuzzy matches for any still-unassigned target ----
    remaining = [c for c in TARGET_COLUMNS if c not in suggestions]
    priority = [c for c in remaining if c in REQUIRED_COLUMNS] + \
               [c for c in remaining if c not in REQUIRED_COLUMNS]
    for target in priority:
        col, score, reason = _best_match_for_target(target, cols, used)
        suggestions[target] = MappingSuggestion(target, col, score, reason)
        if col is not None and score >= 0.75:
            used.add(col)

    return {t: suggestions[t] for t in TARGET_COLUMNS}


def to_dict(s: MappingSuggestion) -> dict:
    return {
        "target_column": s.target_column,
        "source_column": s.source_column,
        "confidence": s.confidence,
        "rationale": s.rationale,
    }
