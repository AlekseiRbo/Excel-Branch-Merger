from pathlib import Path

import pandas as pd

from src.excel_branch_merger.merger import process_folder


def _config(*, unmapped_columns: str = "preserve") -> dict:
    return {
        "input": {
            "csv": {
                "encoding": "utf-8-sig",
                "delimiter": ",",
            },
            "unmapped_columns": unmapped_columns,
        },
        "fields": {
            "customer_name": {
                "aliases": [
                    "Customer Name",
                    "Customer",
                    "Client Name",
                ],
                "required": True,
                "type": "text",
                "case": "preserve",
            },
            "sale_date": {
                "aliases": [
                    "Sale Date",
                    "Date",
                    "Transaction Date",
                ],
                "required": True,
                "type": "date",
                "case": "preserve",
                "formats": ["%Y-%m-%d"],
            },
            "amount": {
                "aliases": [
                    "Amount",
                    "Total",
                ],
                "required": True,
                "type": "number",
                "case": "preserve",
            },
        },
        "deduplication": {
            "keys": [],
            "keep": "first",
        },
        "missing_values": ["", "N/A", "NA", "null"],
        "output": {
            "include_source_lineage": True,
        },
    }


def test_new_fields_contract_maps_aliases_case_insensitively(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "  CUSTOMER   NAME  ": "Alpha",
                " SALE DATE ": "2026-08-01",
                "TOTAL": 100,
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
        _config(),
    )

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Data",
    )

    assert consolidated.loc[0, "customer_name"] == "Alpha"
    assert consolidated.loc[0, "amount"] == 100
    assert "sale_date" in consolidated.columns


def test_canonical_field_name_is_also_a_valid_input_header(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "customer_name": "Beta",
                "sale_date": "2026-08-02",
                "amount": 200,
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
        _config(),
    )

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Data",
    )

    assert consolidated.loc[0, "customer_name"] == "Beta"
    assert consolidated.loc[0, "amount"] == 200


def test_unmapped_columns_are_preserved_when_configured(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Gamma",
                "Date": "2026-08-03",
                "Amount": 300,
                "Notes": "keep me",
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
        _config(unmapped_columns="preserve"),
    )

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Data",
    )

    assert consolidated.loc[0, "Notes"] == "keep me"


def test_unmapped_columns_are_dropped_when_configured(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer": "Delta",
                "Date": "2026-08-04",
                "Amount": 400,
                "Notes": "drop me",
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
        _config(unmapped_columns="drop"),
    )

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Data",
    )

    assert "Notes" not in consolidated.columns


def test_multiple_input_columns_mapping_to_one_field_fail_explicitly(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer Name": "Echo",
                "Customer": "Echo Duplicate",
                "Date": "2026-08-05",
                "Amount": 500,
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
        _config(),
    )

    errors = pd.read_excel(
        result.error_path,
        sheet_name="Errors",
    )

    assert result.files_failed == 1
    assert not errors.empty
    assert errors.loc[0, "source_file"] == "sales.csv"
    assert "same canonical field" in str(errors.loc[0, "validation_errors"]).lower()
