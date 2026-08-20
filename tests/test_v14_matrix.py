from pathlib import Path

import pandas as pd

from src.excel_branch_merger.config import load_config
from src.excel_branch_merger.merger import process_folder

PROCESSING_YAML = """\
input:
  csv:
    encoding: utf-8-sig
    delimiter: ","
  unmapped_columns: preserve

fields:
  customer_name:
    aliases:
      - Customer
      - Customer Name
    required: true
    type: text
    case: preserve

  email:
    aliases:
      - Email
      - E-mail
    required: true
    type: email
    case: lower

  amount:
    aliases:
      - Amount
      - Total
    required: true
    type: number

  invoice_date:
    aliases:
      - Date
      - Invoice Date
    required: true
    type: date
    formats:
      - "%Y-%m-%d"
      - "%d/%m/%Y"

deduplication:
  keys:
    - email
    - invoice_date
  keep: first

missing_values:
  - ""
  - N/A
  - NA
  - "null"

output:
  include_source_lineage: true
"""


def load_processing_config(tmp_path: Path) -> dict:
    config_path = tmp_path / "processing.yaml"
    config_path.write_text(PROCESSING_YAML, encoding="utf-8")
    return load_config(config_path)


def test_v14_csv_only_full_pipeline_from_yaml(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "  Alice   Smith  ",
                "Email": " ALICE@EXAMPLE.COM ",
                "Amount": "1,250.50",
                "Date": "20/08/2026",
            }
        ]
    ).to_csv(
        input_dir / "customers.csv",
        index=False,
        encoding="utf-8-sig",
    )

    result = process_folder(
        input_dir,
        output_dir,
        load_processing_config(tmp_path),
    )

    data = pd.read_excel(result.report_path, sheet_name="Data")

    assert result.files_discovered == 1
    assert result.valid_rows == 1
    assert result.invalid_rows == 0
    assert result.duplicate_rows == 0

    assert data.loc[0, "customer_name"] == "Alice Smith"
    assert data.loc[0, "email"] == "alice@example.com"
    assert data.loc[0, "amount"] == 1250.50
    assert str(data.loc[0, "invoice_date"]).startswith("2026-08-20")

    assert data.loc[0, "source_file"] == "customers.csv"
    assert data.loc[0, "source_sheet"] == "CSV"
    assert data.loc[0, "source_row"] == 2


def test_v14_xlsx_only_full_pipeline_from_yaml(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer Name": "Bob",
                "E-mail": "BOB@EXAMPLE.COM",
                "Total": "500",
                "Invoice Date": "2026-08-20",
            },
            {
                "Customer Name": "Broken",
                "E-mail": "not-an-email",
                "Total": "900",
                "Invoice Date": "2026-08-20",
            },
        ]
    ).to_excel(
        input_dir / "customers.xlsx",
        sheet_name="Sales",
        index=False,
    )

    result = process_folder(
        input_dir,
        output_dir,
        load_processing_config(tmp_path),
    )

    data = pd.read_excel(result.report_path, sheet_name="Data")
    errors = pd.read_excel(result.error_path, sheet_name="Errors")

    assert result.files_discovered == 1
    assert result.total_input_rows == 2
    assert result.valid_rows == 1
    assert result.invalid_rows == 1
    assert result.duplicate_rows == 0

    assert data.loc[0, "customer_name"] == "Bob"
    assert data.loc[0, "email"] == "bob@example.com"
    assert data.loc[0, "source_file"] == "customers.xlsx"
    assert data.loc[0, "source_sheet"] == "Sales"
    assert data.loc[0, "source_row"] == 2

    assert len(errors) == 1
    assert errors.loc[0, "source_file"] == "customers.xlsx"
    assert errors.loc[0, "source_sheet"] == "Sales"
    assert errors.loc[0, "source_row"] == 3
    assert "email" in str(errors.loc[0, "validation_errors"]).lower()


def test_v14_mixed_formats_share_cleaning_validation_and_dedup(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": " Alice ",
                "Email": "ALICE@EXAMPLE.COM",
                "Amount": "1,250.50",
                "Date": "20/08/2026",
            }
        ]
    ).to_excel(
        input_dir / "a.xlsx",
        sheet_name="Sales",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "Customer Name": "Alice",
                "E-mail": " alice@example.com ",
                "Total": "1250.50",
                "Invoice Date": "2026-08-20",
            },
            {
                "Customer Name": "Charlie",
                "E-mail": "charlie@example.com",
                "Total": "700",
                "Invoice Date": "2026-08-21",
            },
        ]
    ).to_csv(
        input_dir / "b.csv",
        index=False,
        encoding="utf-8-sig",
    )

    result = process_folder(
        input_dir,
        output_dir,
        load_processing_config(tmp_path),
    )

    data = pd.read_excel(result.report_path, sheet_name="Data")
    errors = pd.read_excel(result.error_path, sheet_name="Errors")

    assert result.files_discovered == 2
    assert result.total_input_rows == 3
    assert result.valid_rows == 2
    assert result.invalid_rows == 0
    assert result.duplicate_rows == 1

    assert set(data["email"]) == {
        "alice@example.com",
        "charlie@example.com",
    }

    alice = data.loc[data["email"] == "alice@example.com"].iloc[0]
    assert alice["source_file"] == "a.xlsx"
    assert alice["source_sheet"] == "Sales"
    assert alice["source_row"] == 2

    duplicate = errors.loc[
        errors["validation_errors"].astype(str).str.contains("Duplicate record")
    ].iloc[0]

    assert duplicate["source_file"] == "b.csv"
    assert duplicate["source_sheet"] == "CSV"
    assert duplicate["source_row"] == 2

    assert result.total_input_rows == (
        result.valid_rows + result.invalid_rows + result.duplicate_rows
    )
