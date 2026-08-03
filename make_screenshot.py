from __future__ import annotations

import sys
from pathlib import Path

from PIL import ImageGrab

from gui import ExcelBranchMergerApp
from src.excel_branch_merger.config import load_config
from src.excel_branch_merger.merger import process_folder


GENERATED_OUTPUTS = (
    "consolidated_report.xlsx",
    "error_report.xlsx",
    "processing_log.txt",
)


def clean_generated_outputs(output_dir: Path) -> None:
    """Remove reports created only for the screenshot preview."""
    for filename in GENERATED_OUTPUTS:
        path = output_dir / filename
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    input_dir = project_dir / "input"
    output_dir = project_dir / "output"
    screenshot_dir = project_dir / "screenshots"
    screenshot_path = screenshot_dir / "application.png"

    app = ExcelBranchMergerApp()

    try:
        app.update_idletasks()

        config = load_config(project_dir / "config.json")
        result = process_folder(input_dir, output_dir, config)
        app._handle_success(result)

        # Keep the portfolio screenshot free from personal machine paths.
        app.input_var.set(r".\input")
        app.output_var.set(r".\output")

        app.lift()
        app.attributes("-topmost", True)
        app.update_idletasks()
        app.update()

        x = app.winfo_rootx()
        y = app.winfo_rooty()
        width = app.winfo_width()
        height = app.winfo_height()

        screenshot_dir.mkdir(parents=True, exist_ok=True)
        image = ImageGrab.grab(
            bbox=(x, y, x + width, y + height),
            all_screens=True,
        )
        image.save(screenshot_path, format="PNG")

        print(f"Screenshot saved: {screenshot_path}")
        print(
            "Metrics: "
            f"files={result.files_processed}, "
            f"valid={result.valid_rows}, "
            f"errors={result.error_rows}, "
            f"duplicates={result.duplicates_removed}"
        )
    finally:
        app.destroy()
        clean_generated_outputs(output_dir)


if __name__ == "__main__":
    if sys.platform != "win32" and not sys.platform.startswith("linux"):
        raise RuntimeError("Screenshot generation is supported on Windows and Linux.")
    main()
