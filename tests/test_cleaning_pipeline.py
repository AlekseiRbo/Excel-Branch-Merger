from pathlib import Path

import pandas as pd

from src.excel_branch_merger.merger import process_folder

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
        "sale_date": {
            "aliases": ["Date"],
            "required": True,
            "type": "date",
            "case": "preserve",
            "formats": [
                "%Y-%m-%d",
                "%d/%m/%Y",
            ],
        },
        "amount": {
            "aliases": ["Amount"],
            "required": True,
            "type": "number",
            "case": "preserve",
        },
    },
    "deduplication": {
        "keys": [],
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


def test_cleaning_runs_before_validation(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": " N/A ",
                "Email": " SALES@EXAMPLE.COM ",
                "Date": "2026-08-20",
                "Amount": "1,250.50",
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

    errors = pd.read_excel(
        result.error_path,
        sheet_name="Errors",
    )

    assert result.invalid_rows == 1
    assert result.valid_rows == 0
    assert "Missing required field: customer_name" in str(
        errors.loc[0, "validation_errors"]
    )


def test_cleaned_values_reach_consolidated_output(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "  Alpha    Trading  ",
                "Email": " SALES.Team@Example.COM ",
                "Date": "21/08/2026",
                "Amount": "1,250.50",
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

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Consolidated",
    )

    assert result.valid_rows == 1
    assert consolidated.loc[0, "customer_name"] == "Alpha Trading"
    assert consolidated.loc[0, "email"] == "sales.team@example.com"
    assert consolidated.loc[0, "amount"] == 1250.50
