from app.os_catalog import (
    CANONICAL_NAMES,
    GCE_OS_CATALOG,
    canonicalize_os,
    classify_os_type,
    is_canonical,
    is_generic,
    lookup,
    suggest_for,
    to_jsonable,
)


def test_catalog_contains_required_families():
    names = {e.name for e in GCE_OS_CATALOG}
    for must in [
        "Windows Server 2022 Datacenter",
        "Windows Server 2019 Datacenter",
        "Windows Server 2016 Datacenter",
        "Windows Server 2012 R2 Datacenter",
        "Ubuntu 24.04 LTS",
        "Ubuntu 22.04 LTS",
        "Ubuntu 20.04 LTS",
        "Debian 12",
        "Red Hat Enterprise Linux 9",
        "Red Hat Enterprise Linux 8",
        "Rocky Linux 9",
        "AlmaLinux 9",
        "SUSE Linux Enterprise Server 15",
        "Oracle Linux 9",
        "CentOS Stream 9",
    ]:
        assert must in names, f"missing {must}"


def test_classify_windows():
    assert classify_os_type("Windows Server 2019 Datacenter") == "WINDOWS"
    assert classify_os_type("Windows Server 2022") == "WINDOWS"
    assert classify_os_type("Microsoft Windows 10") == "WINDOWS"


def test_classify_linux():
    assert classify_os_type("Ubuntu 22.04 LTS") == "LINUX"
    assert classify_os_type("Red Hat Enterprise Linux 8") == "LINUX"
    assert classify_os_type("CentOS 7") == "LINUX"
    assert classify_os_type("Rocky Linux 9") == "LINUX"


def test_classify_unknown():
    assert classify_os_type("") == "UNKNOWN"
    assert classify_os_type(None) == "UNKNOWN"
    assert classify_os_type("Some random text") == "UNKNOWN"


def test_is_generic_true_for_placeholders():
    for g in ["windows", "Windows", " WINDOWS ", "Linux", "RHEL", "ubuntu", "unknown"]:
        assert is_generic(g), f"{g!r} should be generic"


def test_is_generic_false_for_real_values():
    for real in [
        "Windows Server 2019 Datacenter",
        "Ubuntu 22.04 LTS",
        "Red Hat Enterprise Linux 8",
        "Rocky Linux 9",
    ]:
        assert not is_generic(real), f"{real!r} should NOT be generic"


def test_is_generic_empty_is_not_generic():
    # Empty is "missing" — handled separately by validator.
    assert not is_generic("")
    assert not is_generic(None)


def test_is_canonical_true_only_for_exact_match():
    assert is_canonical("Ubuntu 22.04 LTS")
    assert not is_canonical("ubuntu 22.04 lts")  # case-sensitive
    assert not is_canonical("Ubuntu")
    assert not is_canonical("")


def test_canonicalize_exact_alias():
    assert canonicalize_os("rhel 8") == "Red Hat Enterprise Linux 8"
    assert canonicalize_os("Ubuntu 22.04") == "Ubuntu 22.04 LTS"
    assert canonicalize_os("WINDOWS SERVER 2019") == "Windows Server 2019 Datacenter"


def test_canonicalize_loose_substring():
    # Source mentions edition that's not in our list — fall through to base version
    assert canonicalize_os("Windows Server 2019 Standard Edition") == "Windows Server 2019 Datacenter"
    # Only family + version words present
    assert canonicalize_os("Red Hat Enterprise Linux 9 Server") == "Red Hat Enterprise Linux 9"


def test_canonicalize_no_match_returns_none():
    assert canonicalize_os("AmigaOS 4") is None
    assert canonicalize_os("Solaris 11") is None
    assert canonicalize_os("") is None
    assert canonicalize_os(None) is None


def test_suggest_for_generic_windows():
    s = suggest_for("Windows")
    assert "Windows Server 2022 Datacenter" in s
    assert "Windows Server 2019 Datacenter" in s


def test_suggest_for_generic_linux():
    s = suggest_for("Linux")
    assert any("Ubuntu" in x for x in s)


def test_suggest_for_rhel_alias():
    s = suggest_for("RHEL")
    assert "Red Hat Enterprise Linux 9" in s


def test_suggest_for_empty_returns_unknown_default():
    s = suggest_for("")
    assert len(s) > 0


def test_lookup_returns_entry():
    e = lookup("Ubuntu 22.04 LTS")
    assert e is not None
    assert e.publisher == "Canonical"
    assert e.version == "22.04"
    assert e.type == "LINUX"


def test_to_jsonable_shape():
    j = to_jsonable()
    assert "options" in j and "generic_values" in j and "suggestions" in j
    assert len(j["options"]) == len(GCE_OS_CATALOG)
    for opt in j["options"]:
        assert set(opt.keys()) == {"name", "type", "publisher", "version"}


def test_canonical_names_set_matches_catalog():
    assert CANONICAL_NAMES == frozenset(e.name for e in GCE_OS_CATALOG)
