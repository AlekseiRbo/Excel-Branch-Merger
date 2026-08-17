from pathlib import Path

import pandas as pd

from src.excel_branch_merger.merger import ProcessingStatus, process_folder

CONFIG = {
    "canonical_columns": {
        "customer_name": ["Customer"],
        "sale_date": ["Date"],
        "amount": ["Amount"],
        "invoice_number": ["Invoice"],
    },
    "required_fields": ["customer_name", "sale_date", "amount"],
    "duplicate_key": ["customer_name", "sale_date", "amount", "invoice_number"],
    "date_formats": ["%Y-%m-%d"],
}


def _valid(path: Path) -> None:
    pd.DataFrame(
        {
            "Customer": ["Alice"],
            "Date": ["2026-08-01"],
            "Amount": [100],
            "Invoice": ["A-1"],
        }
    ).to_excel(path, index=False)


def test_only_corrupted_workbook_is_failed(tmp_path: Path) -> None:
    inp = tmp_path / "input"
    inp.mkdir()
    out = tmp_path / "output"
    (inp / "broken.xlsx").write_bytes(b"broken")
    result = process_folder(inp, out, CONFIG)
    assert result.status is ProcessingStatus.FAILED
    assert result.files_discovered == 1
    assert result.files_failed == 1 and result.files_succeeded == 0
    assert result.worksheets_failed == 1


def test_mixed_good_and_corrupted_is_warning(tmp_path: Path) -> None:
    inp = tmp_path / "input"
    inp.mkdir()
    out = tmp_path / "output"
    _valid(inp / "good.xlsx")
    (inp / "broken.xlsx").write_bytes(b"broken")
    result = process_folder(inp, out, CONFIG)
    assert result.status is ProcessingStatus.COMPLETED_WITH_WARNINGS
    assert result.files_discovered == 2
    assert result.files_succeeded == 1 and result.files_failed == 1


def test_all_good_is_success(tmp_path: Path) -> None:
    inp = tmp_path / "input"
    inp.mkdir()
    out = tmp_path / "output"
    _valid(inp / "good.xlsx")
    result = process_folder(inp, out, CONFIG)
    assert result.status is ProcessingStatus.SUCCESS
