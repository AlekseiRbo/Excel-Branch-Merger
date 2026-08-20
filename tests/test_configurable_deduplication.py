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
        "invoice_date": {
            "aliases": ["Date"],
            "required": True,
            "type": "date",
            "formats": [
                "%Y-%m-%d",
                "%d/%m/%Y",
            ],
        },
        "amount": {
            "aliases": ["Amount"],
            "required": True,
            "type": "number",
        },
    },
    "deduplication": {
        "keys": ["email", "invoice_date"],
        "keep": "first",
    },
    "missing_values": [
        "",
        "N/A",
        "NA",
        "null",
    ],
    "output": {
        "include_source_lineage": True,
    },
}


def test_configured_dedup_uses_cleaned_values(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Alpha",
                "Email": " SALES@EXAMPLE.COM ",
                "Date": "21/08/2026",
                "Amount": "100",
            },
            {
                "Customer": "Alpha duplicate",
                "Email": "sales@example.com",
                "Date": "2026-08-21",
                "Amount": "200",
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

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Data",
    )
    errors = pd.read_excel(
        result.error_path,
        sheet_name="Errors",
    )

    assert result.valid_rows == 1
    assert result.duplicate_rows == 1
    assert result.duplicates_removed == 1
    assert result.incomplete_dedup_key_rows == 0

    assert consolidated.loc[0, "customer_name"] == "Alpha"
    assert consolidated.loc[0, "email"] == "sales@example.com"
    assert consolidated.loc[0, "source_row"] == 2

    assert "Duplicate record" in str(errors.loc[0, "validation_errors"])
    assert errors.loc[0, "source_row"] == 3


def test_invalid_rows_are_rejected_before_deduplication(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Valid",
                "Email": "sales@example.com",
                "Date": "2026-08-21",
                "Amount": "100",
            },
            {
                "Customer": "Invalid",
                "Email": "sales@example.com",
                "Date": "2026-08-21",
                "Amount": "not-a-number",
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

    assert result.valid_rows == 1
    assert result.invalid_rows == 1
    assert result.duplicate_rows == 0
    assert result.total_rejected_rows == 1


def test_missing_marker_in_dedup_key_is_incomplete_not_duplicate(
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
                "Date": "2026-08-21",
                "Amount": "100",
            },
            {
                "Customer": "Beta",
                "Email": "N/A",
                "Date": "2026-08-21",
                "Amount": "200",
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

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Data",
    )

    assert len(consolidated) == 2
    assert result.valid_rows == 2
    assert result.duplicate_rows == 0
    assert result.incomplete_dedup_key_rows == 2
    assert result.total_rejected_rows == 0
    assert result.status is ProcessingStatus.COMPLETED_WITH_WARNINGS


def test_keep_first_is_deterministic_across_input_files(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "First",
                "Email": "same@example.com",
                "Date": "2026-08-21",
                "Amount": "100",
            }
        ]
    ).to_csv(
        input_dir / "a-first.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        [
            {
                "Customer": "Second",
                "Email": "same@example.com",
                "Date": "21/08/2026",
                "Amount": "200",
            }
        ]
    ).to_excel(
        input_dir / "b-second.xlsx",
        index=False,
    )

    result = process_folder(
        input_dir,
        output_dir,
        CONFIG,
    )

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Data",
    )
    errors = pd.read_excel(
        result.error_path,
        sheet_name="Errors",
    )

    assert result.valid_rows == 1
    assert result.duplicate_rows == 1

    assert consolidated.loc[0, "customer_name"] == "First"
    assert consolidated.loc[0, "source_file"] == "a-first.csv"

    assert errors.loc[0, "source_file"] == "b-second.xlsx"


def test_composite_key_requires_all_values_to_match(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Alpha",
                "Email": "same@example.com",
                "Date": "2026-08-21",
                "Amount": "100",
            },
            {
                "Customer": "Beta",
                "Email": "same@example.com",
                "Date": "2026-08-22",
                "Amount": "200",
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

    assert result.valid_rows == 2
    assert result.duplicate_rows == 0
    assert result.incomplete_dedup_key_rows == 0
