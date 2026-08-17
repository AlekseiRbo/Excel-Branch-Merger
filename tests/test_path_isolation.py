from pathlib import Path

import pandas as pd
import pytest

from src.excel_branch_merger.merger import process_folder

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


def test_same_input_output_folder_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="different"):
        process_folder(tmp_path, tmp_path, CONFIG)


def test_own_outputs_and_excel_lock_files_are_not_inputs(tmp_path: Path) -> None:
    inp = tmp_path / "input"
    inp.mkdir()
    out = tmp_path / "output"
    frame = pd.DataFrame(
        {
            "Customer": ["Alice"],
            "Date": ["2026-08-01"],
            "Amount": [100],
            "Invoice": ["A-1"],
        }
    )
    frame.to_excel(inp / "sales.xlsx", index=False)
    frame.to_excel(inp / "consolidated_report.xlsx", index=False)
    frame.to_excel(inp / "error_report.xlsx", index=False)
    (inp / "~$sales.xlsx").write_bytes(b"not an xlsx")
    result = process_folder(inp, out, CONFIG)
    assert result.files_processed == 1


def test_missing_input_folder_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        process_folder(tmp_path / "missing", tmp_path / "output", CONFIG)


def test_output_folder_is_created(tmp_path: Path) -> None:
    inp = tmp_path / "input"
    inp.mkdir()
    out = tmp_path / "new-output"
    pd.DataFrame(
        {
            "Customer": ["Alice"],
            "Date": ["2026-08-01"],
            "Amount": [100],
            "Invoice": ["A-1"],
        }
    ).to_excel(inp / "sales.xlsx", index=False)
    result = process_folder(inp, out, CONFIG)
    assert out.is_dir()
    assert (
        result.report_path.exists()
        and result.error_path.exists()
        and result.log_path.exists()
    )
