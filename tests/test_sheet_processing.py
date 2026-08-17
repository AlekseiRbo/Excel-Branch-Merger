from pathlib import Path

import pandas as pd

from src.excel_branch_merger.merger import process_folder


def _config() -> dict:
    return {
        "canonical_columns": {
            "branch": ["Branch", "Office"],
            "customer_name": ["Customer Name", "Client"],
            "sale_date": ["Sale Date", "Date"],
            "amount": ["Amount", "Total"],
            "invoice_number": ["Invoice", "Invoice Number"],
        },
        "required_fields": ["customer_name", "sale_date", "amount"],
        "duplicate_key": ["customer_name", "sale_date", "amount", "invoice_number"],
        "date_formats": ["%Y-%m-%d"],
    }


def test_each_worksheet_is_normalized_before_combining(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    workbook = input_dir / "branches.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Customer Name": ["Alice"],
                "Sale Date": ["2026-08-01"],
                "Amount": [100],
                "Invoice": ["A-1"],
                "Branch": ["North"],
            }
        ).to_excel(writer, sheet_name="North", index=False)
        pd.DataFrame(
            {
                "Client": ["Bob"],
                "Date": ["2026-08-02"],
                "Total": [200],
                "Invoice Number": ["B-1"],
                "Office": ["South"],
            }
        ).to_excel(writer, sheet_name="South", index=False)

    result = process_folder(input_dir, output_dir, _config())
    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    assert set(consolidated["customer_name"]) == {"Alice", "Bob"}
    assert set(consolidated["source_sheet"]) == {"North", "South"}
    assert set(consolidated["source_file"]) == {"branches.xlsx"}
    assert set(consolidated["source_row"]) == {2}


def test_bad_sheet_does_not_discard_good_sheet(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    workbook = input_dir / "mixed.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Customer Name": ["Alice"],
                "Sale Date": ["2026-08-01"],
                "Amount": [100],
                "Invoice": ["A-1"],
            }
        ).to_excel(writer, sheet_name="Good", index=False)
        pd.DataFrame({"Unknown": ["x"]}).to_excel(writer, sheet_name="Bad", index=False)
    result = process_folder(input_dir, output_dir, _config())
    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    errors = pd.read_excel(result.error_path, sheet_name="Errors")
    assert consolidated["customer_name"].tolist() == ["Alice"]
    assert "mixed.xlsx::Good" in result.worksheet_successes
    assert "mixed.xlsx::Bad" in result.worksheet_failures
    assert errors["source_sheet"].tolist() == ["Bad"]


def test_blank_worksheet_does_not_break_other_sheets(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    workbook = input_dir / "with_blank.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Customer Name": ["Alice"],
                "Sale Date": ["2026-08-01"],
                "Amount": [100],
                "Invoice": ["A-1"],
            }
        ).to_excel(writer, sheet_name="Data", index=False)
        pd.DataFrame().to_excel(writer, sheet_name="Blank", index=False)
    result = process_folder(input_dir, output_dir, _config())
    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    assert consolidated["customer_name"].tolist() == ["Alice"]
    assert "with_blank.xlsx::Data" in result.worksheet_successes
