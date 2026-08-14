from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from src.excel_branch_merger.merger import ProcessingStatus, process_folder


CONFIG = {
    "canonical_columns": {
        "branch": ["Branch", "Office"],
        "customer_name": ["Customer", "Client"],
        "sale_date": ["Date", "Sale Date"],
        "amount": ["Amount", "Total"],
        "invoice_number": ["Invoice", "Invoice Number"],
    },
    "required_fields": ["customer_name", "sale_date", "amount"],
    "duplicate_key": ["customer_name", "sale_date", "amount", "invoice_number"],
    "date_formats": ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"],
}


def _valid_frame(customer: str = "Alice", invoice: str = "A-1") -> pd.DataFrame:
    return pd.DataFrame({
        "Customer": [customer],
        "Date": ["2026-08-01"],
        "Amount": [100],
        "Invoice": [invoice],
        "Branch": ["North"],
    })


def _openable(path: Path) -> None:
    workbook = openpyxl.load_workbook(path, read_only=True)
    workbook.close()


def test_end_to_end_multi_file_multi_sheet_outputs(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    with pd.ExcelWriter(inp / "a.xlsx", engine="openpyxl") as writer:
        pd.DataFrame({
            "Customer": ["Alice", "Bad"],
            "Date": ["2026-08-01", "08/04/2026"],
            "Amount": [100, 200],
            "Invoice": ["A-1", "X-1"],
            "Branch": ["N", "N"],
        }).to_excel(writer, sheet_name="One", index=False)
        pd.DataFrame({
            "Client": ["Bob"], "Sale Date": ["2026-08-02"],
            "Total": [300], "Invoice Number": ["B-1"], "Office": ["S"],
        }).to_excel(writer, sheet_name="Two", index=False)
    _valid_frame().to_excel(inp / "b.xlsx", index=False)

    result = process_folder(inp, out, CONFIG)

    assert result.status is ProcessingStatus.SUCCESS
    assert result.total_input_rows == 4
    assert result.valid_rows == 2
    assert result.invalid_rows == 1
    assert result.duplicate_rows == 1
    assert result.total_rejected_rows == 2

    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    errors = pd.read_excel(result.error_path, sheet_name="Errors")
    summary = pd.read_excel(result.report_path, sheet_name="Summary")
    assert set(consolidated["customer_name"]) == {"Alice", "Bob"}
    assert set(consolidated["source_file"]) == {"a.xlsx"}
    assert set(consolidated["source_sheet"]) == {"One", "Two"}
    assert set(consolidated["source_row"]) == {2}
    assert len(errors) == 2
    values = dict(zip(summary["Metric"], summary["Value"]))
    assert values["Total input rows"] == 4
    assert values["Total rejected rows"] == 2
    assert "SUMMARY Total rejected rows: 2" in result.log_path.read_text(encoding="utf-8")
    _openable(result.report_path); _openable(result.error_path)


def test_corrupted_only_is_failed_but_reports_are_created(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    (inp / "broken.xlsx").write_bytes(b"not-an-xlsx")
    result = process_folder(inp, out, CONFIG)
    assert result.status is ProcessingStatus.FAILED
    assert result.files_failed == 1 and result.files_succeeded == 0
    errors = pd.read_excel(result.error_path, sheet_name="Errors")
    assert errors["source_file"].tolist() == ["broken.xlsx"]
    _openable(result.report_path); _openable(result.error_path)


def test_mixed_good_and_corrupted_is_warning(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    _valid_frame().to_excel(inp / "good.xlsx", index=False)
    (inp / "broken.xlsx").write_bytes(b"broken")
    result = process_folder(inp, out, CONFIG)
    assert result.status is ProcessingStatus.COMPLETED_WITH_WARNINGS
    assert result.files_succeeded == 1 and result.files_failed == 1
    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    assert consolidated["customer_name"].tolist() == ["Alice"]


def test_bad_sheet_does_not_remove_good_sheet(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    with pd.ExcelWriter(inp / "mixed.xlsx", engine="openpyxl") as writer:
        _valid_frame().to_excel(writer, sheet_name="Good", index=False)
        pd.DataFrame({"Unknown": ["x"]}).to_excel(writer, sheet_name="Bad", index=False)
    result = process_folder(inp, out, CONFIG)
    assert result.status is ProcessingStatus.COMPLETED_WITH_WARNINGS
    assert result.valid_rows == 1
    assert result.worksheets_succeeded == 1
    assert result.worksheets_failed == 1


def test_all_invalid_rows_still_generate_complete_output_set(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    pd.DataFrame({
        "Customer": ["Bad"], "Date": ["not-a-date"],
        "Amount": ["12abc34"], "Invoice": ["X-1"],
    }).to_excel(inp / "invalid.xlsx", index=False)
    result = process_folder(inp, out, CONFIG)
    assert result.valid_rows == 0
    assert result.invalid_rows == 1
    assert pd.read_excel(result.report_path, sheet_name="Consolidated").empty
    assert len(pd.read_excel(result.error_path, sheet_name="Errors")) == 1
    _openable(result.report_path); _openable(result.error_path)


def test_incomplete_duplicate_keys_are_kept_and_reported(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    pd.DataFrame({
        "Customer": ["Alice", "Alice"],
        "Date": ["2026-08-01", "2026-08-01"],
        "Amount": [100, 100],
        "Invoice": [None, None],
    }).to_excel(inp / "sales.xlsx", index=False)
    result = process_folder(inp, out, CONFIG)
    assert result.valid_rows == 2
    assert result.duplicate_rows == 0
    assert result.incomplete_dedup_key_rows == 2
    assert result.status is ProcessingStatus.COMPLETED_WITH_WARNINGS


def test_same_input_and_output_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="different"):
        process_folder(tmp_path, tmp_path, CONFIG)
