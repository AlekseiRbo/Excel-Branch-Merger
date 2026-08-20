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
        "contact_email": {
            "aliases": ["Email"],
            "required": True,
            "type": "email",
            "case": "lower",
        },
        "invoice_total": {
            "aliases": ["Total"],
            "required": True,
            "type": "number",
            "case": "preserve",
        },
        "invoice_date": {
            "aliases": ["Invoice Date"],
            "required": True,
            "type": "date",
            "case": "preserve",
            "formats": [
                "%Y-%m-%d",
                "%d/%m/%Y",
            ],
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


def test_configured_types_accept_valid_values(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Alpha",
                "Email": " SALES@EXAMPLE.COM ",
                "Total": "1,250.50",
                "Invoice Date": "21/08/2026",
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
    assert result.invalid_rows == 0
    assert consolidated.loc[0, "contact_email"] == "sales@example.com"
    assert consolidated.loc[0, "invoice_total"] == 1250.50
    assert str(consolidated.loc[0, "invoice_date"])[:10] == "2026-08-21"


def test_invalid_email_is_rejected(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Beta",
                "Email": "not-an-email",
                "Total": "500",
                "Invoice Date": "2026-08-20",
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
    assert "Invalid contact_email" in str(errors.loc[0, "validation_errors"])


def test_invalid_configured_number_is_rejected(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Gamma",
                "Email": "gamma@example.com",
                "Total": "not-a-number",
                "Invoice Date": "2026-08-20",
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
    assert "Invalid invoice_total" in str(errors.loc[0, "validation_errors"])


def test_invalid_configured_date_is_rejected(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Delta",
                "Email": "delta@example.com",
                "Total": "750",
                "Invoice Date": "not-a-date",
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
    assert "Invalid invoice_date" in str(errors.loc[0, "validation_errors"])


def test_ambiguous_configured_date_is_rejected(tmp_path: Path) -> None:
    config = {
        **CONFIG,
        "fields": {
            **CONFIG["fields"],
            "invoice_date": {
                **CONFIG["fields"]["invoice_date"],
                "formats": [
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                ],
            },
        },
    }

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Echo",
                "Email": "echo@example.com",
                "Total": "900",
                "Invoice Date": "08/04/2026",
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
        config,
    )

    errors = pd.read_excel(
        result.error_path,
        sheet_name="Errors",
    )

    assert result.invalid_rows == 1
    assert "Ambiguous invoice_date" in str(errors.loc[0, "validation_errors"])


def test_required_rule_works_for_any_configured_field(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Foxtrot",
                "Email": "N/A",
                "Total": "1000",
                "Invoice Date": "2026-08-20",
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
    assert "Missing required field: contact_email" in str(
        errors.loc[0, "validation_errors"]
    )
