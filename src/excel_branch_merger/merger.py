from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .validators import normalize_columns, validate_dataframe
from .version import APP_NAME, __version__


@dataclass(frozen=True)
class ProcessingResult:
    files_processed: int
    valid_rows: int
    error_rows: int
    duplicates_removed: int
    report_path: Path
    error_path: Path
    log_path: Path


ProgressCallback = Callable[[int, int, str], None]


def read_excel_file(path: Path) -> pd.DataFrame:
    workbook = pd.ExcelFile(path)
    frames: list[pd.DataFrame] = []

    for sheet_name in workbook.sheet_names:
        frame = pd.read_excel(workbook, sheet_name=sheet_name)
        if frame.empty:
            continue

        frame["_source_file"] = path.name
        frame["_source_sheet"] = sheet_name
        frame["_source_row"] = range(2, len(frame) + 2)
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def autosize_worksheet(
    writer: pd.ExcelWriter,
    sheet_name: str,
    dataframe: pd.DataFrame,
) -> None:
    worksheet = writer.sheets[sheet_name]

    for index, column in enumerate(dataframe.columns, start=1):
        values = dataframe[column].astype("string").fillna("")
        width = min(max(len(str(column)), values.str.len().max()) + 2, 45)
        worksheet.column_dimensions[
            worksheet.cell(row=1, column=index).column_letter
        ].width = width

        if str(column) == "sale_date":
            for row in worksheet.iter_rows(
                min_row=2,
                max_row=worksheet.max_row,
                min_col=index,
                max_col=index,
            ):
                row[0].number_format = "yyyy-mm-dd"

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions


def process_folder(
    input_dir: Path,
    output_dir: Path,
    config: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
) -> ProcessingResult:
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    excel_files = sorted(
        path for path in input_dir.glob("*.xlsx") if not path.name.startswith("~$")
    )

    if not excel_files:
        raise FileNotFoundError(
            f"No .xlsx files found in input folder: {input_dir}"
        )

    valid_frames: list[pd.DataFrame] = []
    error_frames: list[pd.DataFrame] = []
    log_lines: list[str] = []
    total_files = len(excel_files)

    for index, file_path in enumerate(excel_files, start=1):
        try:
            raw_df = read_excel_file(file_path)
            if raw_df.empty:
                log_lines.append(f"SKIPPED | {file_path.name} | no data")
            else:
                normalized_df = normalize_columns(
                    raw_df,
                    config["canonical_columns"],
                )
                validation = validate_dataframe(
                    normalized_df,
                    config["required_fields"],
                    config["date_formats"],
                )

                valid_frames.append(validation.valid_rows)
                error_frames.append(validation.error_rows)
                log_lines.append(
                    f"OK | {file_path.name} | "
                    f"valid={len(validation.valid_rows)} | "
                    f"errors={len(validation.error_rows)}"
                )
        except Exception as exc:
            log_lines.append(
                f"FAILED | {file_path.name} | "
                f"{type(exc).__name__}: {exc}"
            )
            error_frames.append(
                pd.DataFrame(
                    [
                        {
                            "_source_file": file_path.name,
                            "validation_errors": (
                                f"File processing failed: "
                                f"{type(exc).__name__}: {exc}"
                            ),
                        }
                    ]
                )
            )
        finally:
            if progress_callback is not None:
                progress_callback(index, total_files, file_path.name)

    combined_valid = (
        pd.concat(valid_frames, ignore_index=True) if valid_frames else pd.DataFrame()
    )
    non_empty_error_frames = [
        frame for frame in error_frames if not frame.empty and not frame.isna().all().all()
    ]
    combined_errors = (
        pd.concat(non_empty_error_frames, ignore_index=True)
        if non_empty_error_frames
        else pd.DataFrame()
    )

    duplicate_key = [
        field for field in config["duplicate_key"] if field in combined_valid.columns
    ]

    duplicates_removed = 0
    if duplicate_key and not combined_valid.empty:
        duplicate_mask = combined_valid.duplicated(
            subset=duplicate_key,
            keep="first",
        )
        duplicates_removed = int(duplicate_mask.sum())

        duplicate_rows = combined_valid.loc[duplicate_mask].copy()
        if not duplicate_rows.empty:
            duplicate_rows["validation_errors"] = (
                "Duplicate row removed using key: " + ", ".join(duplicate_key)
            )
            combined_errors = pd.concat(
                [combined_errors, duplicate_rows],
                ignore_index=True,
            )

        combined_valid = combined_valid.loc[~duplicate_mask].copy()

    canonical_order = list(config["canonical_columns"].keys())
    metadata_order = ["_source_file", "_source_sheet", "_source_row"]

    ordered_valid_columns = [
        column
        for column in canonical_order + metadata_order
        if column in combined_valid.columns
    ]
    remaining_valid_columns = [
        column
        for column in combined_valid.columns
        if column not in ordered_valid_columns and column != "validation_errors"
    ]
    combined_valid = combined_valid[ordered_valid_columns + remaining_valid_columns]

    report_path = output_dir / "consolidated_report.xlsx"
    error_path = output_dir / "error_report.xlsx"
    log_path = output_dir / "processing_log.txt"

    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        combined_valid.to_excel(writer, sheet_name="Consolidated", index=False)
        autosize_worksheet(writer, "Consolidated", combined_valid)

        summary = pd.DataFrame(
            [
                {"metric": "Files discovered", "value": len(excel_files)},
                {"metric": "Valid rows", "value": len(combined_valid)},
                {"metric": "Error rows", "value": len(combined_errors)},
                {"metric": "Duplicates removed", "value": duplicates_removed},
            ]
        )
        summary.to_excel(writer, sheet_name="Summary", index=False)
        autosize_worksheet(writer, "Summary", summary)

    with pd.ExcelWriter(error_path, engine="openpyxl") as writer:
        combined_errors.to_excel(writer, sheet_name="Errors", index=False)
        autosize_worksheet(writer, "Errors", combined_errors)

    timestamp = datetime.now(timezone.utc).isoformat()
    log_header = [
        f"{APP_NAME} v{__version__} log",
        f"UTC timestamp: {timestamp}",
        f"Input folder: {input_dir}",
        f"Output folder: {output_dir}",
        "",
    ]
    log_path.write_text("\n".join(log_header + log_lines), encoding="utf-8")

    return ProcessingResult(
        files_processed=len(excel_files),
        valid_rows=len(combined_valid),
        error_rows=len(combined_errors),
        duplicates_removed=duplicates_removed,
        report_path=report_path,
        error_path=error_path,
        log_path=log_path,
    )
