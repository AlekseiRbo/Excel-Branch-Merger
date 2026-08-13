from pathlib import Path

from src.excel_branch_merger.config import load_config
from src.excel_branch_merger.merger import ProcessingStatus, process_folder
from src.excel_branch_merger.version import APP_NAME, __version__


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    result = process_folder(
        base_dir / "input",
        base_dir / "output",
        load_config(base_dir / "config.json"),
    )
    print(f"{APP_NAME} v{__version__}")
    print(f"Status: {result.status.value}")
    print(f"Files discovered: {result.files_discovered}")
    print(f"Files succeeded: {result.files_succeeded}")
    print(f"Files failed: {result.files_failed}")
    print(f"Files skipped: {result.files_skipped}")
    print(f"Worksheets succeeded: {result.worksheets_succeeded}")
    print(f"Worksheets failed: {result.worksheets_failed}")
    print(f"Total input rows: {result.total_input_rows}")
    print(f"Valid rows: {result.valid_rows}")
    print(f"Invalid rows: {result.invalid_rows}")
    print(f"Duplicate rows: {result.duplicate_rows}")
    print(f"Incomplete dedup key rows: {result.incomplete_dedup_key_rows}")
    print(f"Total rejected rows: {result.total_rejected_rows}")
    print(f"Report: {result.report_path}")
    print(f"Errors: {result.error_path}")
    print(f"Log: {result.log_path}")
    return 1 if result.status is ProcessingStatus.FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
