from pathlib import Path

from src.excel_branch_merger.config import load_config
from src.excel_branch_merger.merger import ProcessingStatus, process_folder
from src.excel_branch_merger.version import APP_NAME, __version__


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    result = process_folder(base_dir / "input", base_dir / "output", load_config(base_dir / "config.json"))
    print(f"{APP_NAME} v{__version__}")
    print(f"Status: {result.status.value}")
    print(f"Files discovered: {result.files_discovered}")
    print(f"Files succeeded: {result.files_succeeded}")
    print(f"Files failed: {result.files_failed}")
    print(f"Valid rows: {result.valid_rows}")
    print(f"Error rows: {result.error_rows}")
    print(f"Duplicates removed: {result.duplicates_removed}")
    print(f"Report: {result.report_path}")
    print(f"Errors: {result.error_path}")
    print(f"Log: {result.log_path}")
    return 1 if result.status is ProcessingStatus.FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
