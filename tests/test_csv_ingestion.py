from pathlib import Path

import pandas as pd

from src.excel_branch_merger.merger import ProcessingStatus, process_folder

CONFIG = {
    "canonical_columns": {
        "customer_name": ["customer name", "customer"],
        "sale_date": ["sale date", "date"],
        "amount": ["amount", "total"],
        "invoice_number": ["invoice number", "invoice"],
    },
    "required_fields": ["customer_name", "sale_date", "amount"],
    "duplicate_key": [
        "customer_name",
        "sale_date",
        "amount",
        "invoice_number",
    ],
    "date_formats": ["%Y-%m-%d"],
    "input": {
        "csv": {
            "encoding": "utf-8-sig",
            "delimiter": ",",
        }
    },
}


def test_csv_only_input_is_processed(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer Name": "Alpha",
                "Sale Date": "2026-08-01",
                "Amount": 100,
                "Invoice Number": "INV-001",
            },
            {
                "Customer Name": "Beta",
                "Sale Date": "2026-08-02",
                "Amount": 200,
                "Invoice Number": "INV-002",
            },
        ]
    ).to_csv(input_dir / "sales.csv", index=False, encoding="utf-8-sig")

    result = process_folder(input_dir, output_dir, CONFIG)

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Consolidated",
    )

    assert result.status is ProcessingStatus.SUCCESS
    assert result.files_discovered == 1
    assert result.files_succeeded == 1
    assert result.files_failed == 0
    assert result.total_input_rows == 2

    assert len(consolidated) == 2
    assert set(consolidated["source_file"]) == {"sales.csv"}
    assert set(consolidated["source_sheet"]) == {"CSV"}
    assert consolidated["source_row"].tolist() == [2, 3]


def test_mixed_xlsx_and_csv_inputs_share_one_pipeline(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    pd.DataFrame(
        [
            {
                "Customer Name": "Excel Customer",
                "Sale Date": "2026-08-03",
                "Amount": 300,
                "Invoice Number": "INV-XLSX",
            }
        ]
    ).to_excel(input_dir / "branch.xlsx", index=False)

    pd.DataFrame(
        [
            {
                "Customer Name": "CSV Customer",
                "Sale Date": "2026-08-04",
                "Amount": 400,
                "Invoice Number": "INV-CSV",
            }
        ]
    ).to_csv(input_dir / "branch.csv", index=False, encoding="utf-8-sig")

    result = process_folder(input_dir, output_dir, CONFIG)

    consolidated = pd.read_excel(
        result.report_path,
        sheet_name="Consolidated",
    )

    assert result.status is ProcessingStatus.SUCCESS
    assert result.files_discovered == 2
    assert result.files_succeeded == 2
    assert result.files_failed == 0
    assert result.total_input_rows == 2

    assert len(consolidated) == 2
    assert set(consolidated["source_file"]) == {
        "branch.xlsx",
        "branch.csv",
    }
    assert set(consolidated["source_sheet"]) == {
        "Sheet1",
        "CSV",
    }
