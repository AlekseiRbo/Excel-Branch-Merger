from pathlib import Path

import pandas as pd

from src.excel_branch_merger.merger import ProcessingStatus, process_folder

CONFIG = {
    "input": {
        "csv": {
            "encoding": "utf-8-sig",
            "delimiter": ",",
        },
        "unmapped_columns": "preserve",
    },
    "fields": {
        "customer_name": {
            "aliases": ["Customer"],
            "required": True,
            "type": "text",
            "case": "preserve",
        },
        "email": {
            "aliases": ["Email"],
            "required": False,
            "type": "email",
            "case": "lower",
        },
        "amount": {
            "aliases": ["Amount"],
            "required": True,
            "type": "number",
        },
        "invoice_date": {
            "aliases": ["Date"],
            "required": True,
            "type": "date",
            "formats": ["%Y-%m-%d"],
        },
    },
    "deduplication": {
        "keys": ["email", "invoice_date"],
        "keep": "first",
    },
    "missing_values": ["", "N/A", "NA", "null"],
    "output": {
        "include_source_lineage": True,
    },
}


def test_v14_processing_log_has_header_events_summary_and_footer(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Alpha",
                "Email": "alpha@example.com",
                "Amount": "100",
                "Date": "2026-08-20",
            }
        ]
    ).to_csv(
        input_dir / "sales.csv",
        index=False,
        encoding="utf-8-sig",
    )

    result = process_folder(
        input_dir,
        output_dir,
        CONFIG,
    )

    log_text = result.log_path.read_text(encoding="utf-8")
    lines = log_text.splitlines()

    assert result.status is ProcessingStatus.SUCCESS
    assert result.log_path.name == "processing.log"

    assert lines[0] == "START Excel Branch Merger"
    assert "INPUT Files discovered: 1" in lines
    assert "OK sales.csv::CSV: valid=1 errors=0" in lines

    assert "SUMMARY Total input rows: 1" in lines
    assert "SUMMARY Valid rows: 1" in lines
    assert "SUMMARY Invalid rows: 0" in lines
    assert "SUMMARY Duplicate rows: 0" in lines
    assert "SUMMARY Total rejected rows: 0" in lines

    assert ("INVARIANT rows: total_input=1 valid=1 invalid=0 duplicate=0") in lines

    assert "OUTPUT Consolidated.xlsx" in lines
    assert "OUTPUT Errors.xlsx" in lines
    assert "OUTPUT processing.log" in lines

    assert lines[-1] == "STATUS SUCCESS"


def test_v14_processing_log_records_warning_status(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Alpha",
                "Email": "N/A",
                "Amount": "100",
                "Date": "2026-08-20",
            },
            {
                "Customer": "Beta",
                "Email": "N/A",
                "Amount": "200",
                "Date": "2026-08-20",
            },
        ]
    ).to_csv(
        input_dir / "sales.csv",
        index=False,
        encoding="utf-8-sig",
    )

    result = process_folder(
        input_dir,
        output_dir,
        CONFIG,
    )

    log_text = result.log_path.read_text(encoding="utf-8")

    assert result.status is ProcessingStatus.COMPLETED_WITH_WARNINGS
    assert "WARN incomplete duplicate key: 2 row(s)" in log_text
    assert "SUMMARY Incomplete dedup key rows: 2" in log_text
    assert "STATUS COMPLETED_WITH_WARNINGS" in log_text


def test_v14_processing_log_records_failed_input(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "broken.xlsx").write_bytes(b"this is not an Excel workbook")

    result = process_folder(
        input_dir,
        output_dir,
        CONFIG,
    )

    log_text = result.log_path.read_text(encoding="utf-8")

    assert result.status is ProcessingStatus.FAILED
    assert "FAIL broken.xlsx:" in log_text
    assert "SUMMARY Files failed: 1" in log_text
    assert "STATUS FAILED" in log_text


def test_v14_row_invariant_matches_processing_result(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Valid",
                "Email": "same@example.com",
                "Amount": "100",
                "Date": "2026-08-20",
            },
            {
                "Customer": "Duplicate",
                "Email": "same@example.com",
                "Amount": "200",
                "Date": "2026-08-20",
            },
            {
                "Customer": "Invalid",
                "Email": "invalid@example.com",
                "Amount": "not-a-number",
                "Date": "2026-08-20",
            },
        ]
    ).to_csv(
        input_dir / "sales.csv",
        index=False,
        encoding="utf-8-sig",
    )

    result = process_folder(
        input_dir,
        output_dir,
        CONFIG,
    )

    assert result.total_input_rows == (
        result.valid_rows + result.invalid_rows + result.duplicate_rows
    )

    expected = (
        "INVARIANT rows: "
        f"total_input={result.total_input_rows} "
        f"valid={result.valid_rows} "
        f"invalid={result.invalid_rows} "
        f"duplicate={result.duplicate_rows}"
    )

    assert expected in result.log_path.read_text(encoding="utf-8")
