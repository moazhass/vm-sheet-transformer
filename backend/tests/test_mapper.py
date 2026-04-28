from app.mapper import suggest_mapping, TARGET_COLUMNS


def test_target_columns_in_exact_order_and_count():
    assert TARGET_COLUMNS[0] == "MachineId"
    assert TARGET_COLUMNS[-1] == "IsPhysical"
    assert len(TARGET_COLUMNS) == 19


def test_exact_synonym_match_returns_high_confidence():
    src = ["Server Name", "vCPU", "RAM (GB)", "Disk (GB)", "OS", "Status"]
    suggestions = suggest_mapping(src)
    assert suggestions["MachineName"].source_column == "Server Name"
    assert suggestions["MachineName"].confidence >= 0.85
    assert suggestions["AllocatedProcessorCoreCount"].source_column == "vCPU"
    assert suggestions["MemoryGiB"].source_column == "RAM (GB)"
    assert suggestions["TotalDiskAllocatedGiB"].source_column == "Disk (GB)"
    assert suggestions["OsName"].source_column == "OS"
    assert suggestions["MachineStatus(optional)"].source_column == "Status"


def test_machineid_marked_for_generation_when_missing():
    src = ["Server Name", "vCPU", "RAM", "Disk", "OS"]
    suggestions = suggest_mapping(src)
    assert suggestions["MachineId"].source_column is None
    assert "generate" in suggestions["MachineId"].rationale.lower()


def test_fuzzy_match_handles_minor_typos():
    src = ["Hostnme", "CPUs", "Memory GB", "Storage GB", "Operating System"]
    suggestions = suggest_mapping(src)
    assert suggestions["MachineName"].source_column == "Hostnme"
    assert suggestions["AllocatedProcessorCoreCount"].source_column == "CPUs"
    assert suggestions["MemoryGiB"].source_column == "Memory GB"
    assert suggestions["TotalDiskAllocatedGiB"].source_column == "Storage GB"
    assert suggestions["OsName"].source_column == "Operating System"


def test_no_source_column_yields_zero_confidence_for_optional():
    src = ["Server Name", "vCPU", "RAM", "Disk", "OS"]
    suggestions = suggest_mapping(src)
    assert suggestions["PrimaryIPAddress(optional)"].source_column is None
    assert suggestions["PrimaryIPAddress(optional)"].confidence == 0.0


def test_low_confidence_threshold_rejects_unrelated_columns():
    src = ["Color", "Random", "Notes"]
    suggestions = suggest_mapping(src)
    # MachineName must not pick up nonsense columns at high confidence
    if suggestions["MachineName"].source_column is not None:
        assert suggestions["MachineName"].confidence < 0.6


def test_each_target_column_has_a_suggestion_entry():
    src = ["Server Name", "OS"]
    suggestions = suggest_mapping(src)
    for col in TARGET_COLUMNS:
        assert col in suggestions
