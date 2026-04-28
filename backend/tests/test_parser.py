from pathlib import Path

import pandas as pd

from app.parser import detect_header_row, parse_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_header_row_simple():
    rows = pd.DataFrame([
        ["foo", None, None],
        ["Server Name", "vCPU", "RAM"],
        ["host1", 4, 16],
    ])
    idx = detect_header_row(rows)
    assert idx == 1


def test_parse_simple_csv():
    result = parse_file(FIXTURES / "sample_simple.csv")
    sheet = result.sheets[0]
    assert sheet.header_row_index == 0
    assert "Server Name" in sheet.columns
    assert sheet.row_count == 4


def test_parse_messy_csv_skips_preamble():
    result = parse_file(FIXTURES / "sample_messy.csv")
    sheet = result.sheets[0]
    assert sheet.header_row_index >= 2
    assert "Server Name" in sheet.columns
    # Last row has empty server name; row drop policy keeps it; row_count >=2
    assert sheet.row_count >= 2
