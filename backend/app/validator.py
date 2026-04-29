"""Validate transformed rows. Returns structured issues for the UI to render.

Errors block export. Warnings allow export but inform the user.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd

from app.mapper import REQUIRED_COLUMNS
from app.os_catalog import is_canonical, is_generic, suggest_for

NUMERIC_COLUMNS = {
    "TotalDiskAllocatedGiB",
    "TotalDiskUsedGiB",
    "AllocatedProcessorCoreCount",
    "MemoryGiB",
}

# Sanity ceilings for warning detection.
MEMORY_CEILING_GIB = 4096
CPU_CEILING_CORES = 512
DISK_CEILING_GIB = 1_048_576  # 1 PiB


@dataclass
class ValidationIssue:
    row: int  # 1-based
    target_column: str
    severity: str  # "error" | "warning"
    message: str
    suggested_fix: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _is_blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return str(v).strip() == ""


def _is_numeric(v) -> bool:
    if isinstance(v, (int, float)) and not (isinstance(v, float) and pd.isna(v)):
        return True
    try:
        float(str(v).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def _to_float(v) -> float | None:
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def validate(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Duplicate detection passes
    name_counts = Counter(str(v).strip() for v in df.get("MachineName", []) if not _is_blank(v))
    id_counts = Counter(str(v).strip() for v in df.get("MachineId", []) if not _is_blank(v))

    for idx, row in df.iterrows():
        row_num = idx + 1

        # Required-field presence
        for col in REQUIRED_COLUMNS:
            if col not in df.columns or _is_blank(row[col]):
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column=col,
                    severity="error",
                    message=f"Required field '{col}' is missing or empty.",
                    suggested_fix="Provide a source mapping or a default value.",
                ))

        # Numeric-format check for required numeric fields
        for col in NUMERIC_COLUMNS:
            if col in df.columns and not _is_blank(row[col]) and not _is_numeric(row[col]):
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column=col,
                    severity="error",
                    message=f"'{col}' value '{row[col]}' is not numeric.",
                    suggested_fix="Map a numeric source column or correct the cell.",
                ))

        # IsPhysical must be 0 or 1
        if "IsPhysical" in df.columns and not _is_blank(row["IsPhysical"]):
            v = str(row["IsPhysical"]).strip()
            if v not in {"0", "1"}:
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column="IsPhysical",
                    severity="error",
                    message=f"IsPhysical must be 0 or 1; got '{row['IsPhysical']}'.",
                    suggested_fix="Use 0 for VM/cloud, 1 for physical/baremetal.",
                ))

        # Sanity ceilings
        if "MemoryGiB" in df.columns:
            n = _to_float(row["MemoryGiB"])
            if n is not None and n > MEMORY_CEILING_GIB:
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column="MemoryGiB",
                    severity="warning",
                    message=f"MemoryGiB={n:g} exceeds {MEMORY_CEILING_GIB} — verify unit conversion.",
                    suggested_fix="Check whether source unit is MB but unmarked.",
                ))
        if "AllocatedProcessorCoreCount" in df.columns:
            n = _to_float(row["AllocatedProcessorCoreCount"])
            if n is not None and n > CPU_CEILING_CORES:
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column="AllocatedProcessorCoreCount",
                    severity="warning",
                    message=f"AllocatedProcessorCoreCount={n:g} exceeds {CPU_CEILING_CORES}.",
                ))
        if "TotalDiskAllocatedGiB" in df.columns:
            n = _to_float(row["TotalDiskAllocatedGiB"])
            if n is not None and n > DISK_CEILING_GIB:
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column="TotalDiskAllocatedGiB",
                    severity="warning",
                    message=f"TotalDiskAllocatedGiB={n:g} exceeds 1 PiB — verify unit conversion.",
                ))

        # Duplicate MachineId — ERROR per spec (blocks export)
        if "MachineId" in df.columns and not _is_blank(row["MachineId"]):
            if id_counts[str(row["MachineId"]).strip()] > 1:
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column="MachineId",
                    severity="error",
                    message=f"Duplicate MachineId '{row['MachineId']}'.",
                    suggested_fix="Use the bulk action 'Auto-generate missing MachineId' or rename manually.",
                ))

        # Duplicate MachineName — WARNING only when MachineId is also unique.
        # Two rows with the same name BUT distinct MachineIds is acceptable
        # (Migration Center only requires MachineId uniqueness).
        if "MachineName" in df.columns and not _is_blank(row["MachineName"]):
            if name_counts[str(row["MachineName"]).strip()] > 1:
                machine_id = str(row.get("MachineId", "")).strip()
                if machine_id and id_counts.get(machine_id, 0) == 1:
                    issues.append(ValidationIssue(
                        row=row_num,
                        target_column="MachineName",
                        severity="warning",
                        message=f"Duplicate MachineName '{row['MachineName']}' (MachineId is unique, so export is allowed).",
                        suggested_fix="Use bulk action 'Deduplicate MachineName' to append a -02 suffix.",
                    ))

        # OsName quality — generic placeholder is a warning with suggestions
        if "OsName" in df.columns and not _is_blank(row["OsName"]):
            os_name = str(row["OsName"]).strip()
            if is_generic(os_name):
                hints = suggest_for(os_name)
                fix = (
                    "Pick a specific OS in the inline editor. Suggestions: "
                    + ", ".join(hints[:3]) if hints else "Pick a specific OS in the inline editor."
                )
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column="OsName",
                    severity="warning",
                    message=f"Generic OsName '{os_name}' — Migration Center needs the exact version.",
                    suggested_fix=fix,
                ))
            elif not is_canonical(os_name):
                # Not generic, but not in our GCE catalog either — let the user know
                # in case it's a typo or pre-canonicalisation form.
                issues.append(ValidationIssue(
                    row=row_num,
                    target_column="OsName",
                    severity="warning",
                    message=f"OsName '{os_name}' is not in the GCE catalog.",
                    suggested_fix="Select the matching canonical OS from the dropdown.",
                ))

    return issues


def split(issues: Iterable[ValidationIssue]) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return errors, warnings
