from pathlib import Path

from src.excel_branch_merger.config import load_config
from src.excel_branch_merger.merger import process_folder
from src.excel_branch_merger.version import APP_NAME, __version__


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_dir = base_dir / "input"
    output_dir = base_dir / "output"
    config_path = base_dir / "config.json"

    config = load_config(config_path)
    result = process_folder(input_dir, output_dir, config)

    print(f"{APP_NAME} v{__version__}")
    print("Processing completed.")
    print(f"Files processed: {result.files_processed}")
    print(f"Valid rows: {result.valid_rows}")
    print(f"Error rows: {result.error_rows}")
    print(f"Duplicates removed: {result.duplicates_removed}")
    print(f"Report: {result.report_path}")
    print(f"Errors: {result.error_path}")
    print(f"Log: {result.log_path}")


if __name__ == "__main__":
    main()
