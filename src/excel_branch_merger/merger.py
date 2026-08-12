from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from openpyxl.utils import get_column_letter

from .validators import normalize_columns, validate_dataframe

REPORT_NAME = "consolidated_report.xlsx"
ERROR_NAME = "error_report.xlsx"
LOG_NAME = "processing_log.txt"


@dataclass(frozen=True)
class ProcessingResult:
    files_processed: int
    valid_rows: int
    error_rows: int
    duplicates_removed: int
    report_path: Path
    error_path: Path
    log_path: Path
    worksheet_successes: tuple[str, ...] = ()
    worksheet_failures: tuple[str, ...] = ()


def _cfg(config: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in config:
            return config[name]
    return default


def _empty_like(dataframe: pd.DataFrame) -> pd.DataFrame:
    return dataframe.iloc[0:0].copy()


def _source_error_rows(
    dataframe: pd.DataFrame,
    filename: str,
    sheet_name: str,
    message: str,
) -> pd.DataFrame:
    rows = dataframe.copy()
    if rows.empty:
        rows = pd.DataFrame({"validation_errors": [message]})
        rows["source_row"] = pd.NA
    else:
        rows["validation_errors"] = message
        rows["source_row"] = rows.index.to_series().map(lambda value: int(value) + 2)
    rows["source_file"] = filename
    rows["source_sheet"] = sheet_name
    return rows


def _prepare_sheet(
    dataframe: pd.DataFrame,
    *,
    filename: str,
    sheet_name: str,
    canonical_columns: dict[str, list[str]],
    required_fields: list[str],
    date_formats: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    if dataframe.empty and len(dataframe.columns) == 0:
        return dataframe.copy(), dataframe.copy(), True

    normalized = normalize_columns(dataframe, canonical_columns)
    missing_columns = [name for name in required_fields if name not in normalized.columns]
    if missing_columns:
        message = "Missing required column(s): " + ", ".join(missing_columns)
        return _empty_like(normalized), _source_error_rows(
            normalized, filename, sheet_name, message
        ), False

    normalized = normalized.copy()
    normalized["source_file"] = filename
    normalized["source_sheet"] = sheet_name
    normalized["source_row"] = normalized.index.to_series().map(lambda value: int(value) + 2)
    validation = validate_dataframe(normalized, required_fields, date_formats)
    return validation.valid_rows, validation.error_rows, True



def _deduplicate(
    dataframe: pd.DataFrame,
    duplicate_key: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    if dataframe.empty or not duplicate_key:
        return dataframe.copy(), _empty_like(dataframe), 0

    missing_columns = [name for name in duplicate_key if name not in dataframe.columns]
    if missing_columns:
        # Never silently shrink the configured key. Keep rows and report them as
        # incomplete-key rows; RESULT/METRICS tasks expose this count to the UI.
        return dataframe.copy(), _empty_like(dataframe), len(dataframe)

    key_frame = dataframe[duplicate_key]
    complete = pd.Series(True, index=dataframe.index, dtype="bool")
    for name in duplicate_key:
        series = key_frame[name]
        missing = series.isna()
        if series.dtype == "object" or str(series.dtype).startswith("string"):
            missing = missing | series.astype("string").str.strip().eq("")
        complete &= ~missing.fillna(True)

    eligible = dataframe.loc[complete]
    duplicate_mask = eligible.duplicated(subset=duplicate_key, keep="first")
    duplicate_indexes = eligible.index[duplicate_mask]
    duplicates = dataframe.loc[duplicate_indexes].copy()
    if not duplicates.empty:
        duplicates["validation_errors"] = "Duplicate record (complete configured key)"
    kept = dataframe.drop(index=duplicate_indexes).copy()
    incomplete_count = int((~complete).sum())
    return kept, duplicates, incomplete_count



def _autosize_worksheet(worksheet, dataframe: pd.DataFrame) -> None:
    for position, column_name in enumerate(dataframe.columns, start=1):
        header_width = len(str(column_name))
        if dataframe.empty:
            data_width = 0
        else:
            lengths = dataframe[column_name].map(
                lambda value: 0 if pd.isna(value) else len(str(value))
            )
            data_width = int(lengths.max()) if not lengths.empty else 0
        width = min(max(header_width, data_width) + 2, 60)
        worksheet.column_dimensions[get_column_letter(position)].width = width



def _write_dataframe_sheet(writer: pd.ExcelWriter, dataframe: pd.DataFrame, sheet_name: str) -> None:
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
    _autosize_worksheet(writer.book[sheet_name], dataframe)


def _write_report_workbook(path: Path, consolidated: pd.DataFrame, summary: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _write_dataframe_sheet(writer, consolidated, "Consolidated")
        _write_dataframe_sheet(writer, summary, "Summary")


def _write_error_workbook(path: Path, errors: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _write_dataframe_sheet(writer, errors, "Errors")



def _write_outputs(
    output_dir: Path,
    consolidated: pd.DataFrame,
    errors: pd.DataFrame,
    summary: pd.DataFrame,
    log_lines: list[str],
) -> tuple[Path, Path, Path]:
    report_path = output_dir / REPORT_NAME
    error_path = output_dir / ERROR_NAME
    log_path = output_dir / LOG_NAME
    # Legacy direct writes until OUTPUT-08.
    _write_report_workbook(report_path, consolidated, summary)
    _write_error_workbook(error_path, errors)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return report_path, error_path, log_path



def process_folder(
    input_dir: Path,
    output_dir: Path,
    config: dict[str, Any],
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> ProcessingResult:

    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")
    if input_dir == output_dir:
        raise ValueError("Input and output folders must be different.")
    output_dir.mkdir(parents=True, exist_ok=True)
    excluded_names = {REPORT_NAME, ERROR_NAME}
    input_files = sorted(
        path for path in input_dir.glob("*.xlsx")
        if not path.name.startswith("~$")
        and path.name not in excluded_names
        and not path.name.startswith(".")
    )

    canonical_columns = _cfg(config, "canonical_columns", "column_aliases", default={})
    required_fields = list(_cfg(config, "required_fields", default=[]))
    date_formats = list(_cfg(config, "date_formats", default=["%Y-%m-%d"]))
    duplicate_key = list(_cfg(config, "duplicate_key", "duplicate_keys", default=[]))

    valid_parts: list[pd.DataFrame] = []
    error_parts: list[pd.DataFrame] = []
    worksheet_successes: list[str] = []
    worksheet_failures: list[str] = []
    files_succeeded = 0
    files_failed = 0
    files_skipped = 0
    total_input_rows = 0
    log_lines: list[str] = []

    for current, workbook_path in enumerate(input_files, start=1):
        if progress_callback:
            progress_callback(current, len(input_files), workbook_path.name)
        workbook_had_success = False
        workbook_had_sheet = False
        try:
            excel_file = pd.ExcelFile(workbook_path)
            for sheet_name in excel_file.sheet_names:
                frame = pd.read_excel(excel_file, sheet_name=sheet_name)
                if frame.empty and len(frame.columns) == 0:
                    files_skipped += 0
                    log_lines.append(f"SKIP {workbook_path.name}::{sheet_name}: empty worksheet")
                    continue
                workbook_had_sheet = True
                total_input_rows += len(frame)
                try:
                    valid_rows, error_rows, sheet_ok = _prepare_sheet(
                        frame,
                        filename=workbook_path.name,
                        sheet_name=sheet_name,
                        canonical_columns=canonical_columns,
                        required_fields=required_fields,
                        date_formats=date_formats,
                    )
                except Exception as exc:
                    error_rows = _source_error_rows(
                        frame,
                        workbook_path.name,
                        sheet_name,
                        f"Worksheet processing failed: {exc}",
                    )
                    valid_rows = _empty_like(frame)
                    sheet_ok = False
                if not valid_rows.empty:
                    valid_parts.append(valid_rows)
                if not error_rows.empty:
                    error_parts.append(error_rows)
                identity = f"{workbook_path.name}::{sheet_name}"
                if sheet_ok:
                    worksheet_successes.append(identity)
                    workbook_had_success = True
                    log_lines.append(f"OK {identity}: valid={len(valid_rows)} errors={len(error_rows)}")
                else:
                    worksheet_failures.append(identity)
                    log_lines.append(f"FAIL {identity}: errors={len(error_rows)}")
            if workbook_had_success:
                files_succeeded += 1
            elif workbook_had_sheet:
                files_failed += 1
            else:
                files_skipped += 1
                log_lines.append(f"SKIP {workbook_path.name}: no non-empty worksheets")
        except Exception as exc:
            files_failed += 1
            worksheet_failures.append(f"{workbook_path.name}::<workbook>")
            error_parts.append(pd.DataFrame([{
                "source_file": workbook_path.name,
                "source_sheet": pd.NA,
                "source_row": pd.NA,
                "validation_errors": f"Unable to read workbook: {exc}",
            }]))
            log_lines.append(f"FAIL {workbook_path.name}: {exc}")

    if valid_parts:
        combined_valid = pd.concat(valid_parts, ignore_index=True, sort=False)
    else:
        canonical_names = list(canonical_columns.keys())
        combined_valid = pd.DataFrame(columns=canonical_names + ["source_file", "source_sheet", "source_row", "validation_errors"])

    if error_parts:
        validation_errors = pd.concat(error_parts, ignore_index=True, sort=False)
    else:
        validation_errors = _empty_like(combined_valid)

    consolidated, duplicates, incomplete_count = _deduplicate(combined_valid, duplicate_key)
    if incomplete_count:
        log_lines.append(
            f"WARN incomplete duplicate key: {incomplete_count} row(s) kept and excluded from deduplication"
        )
    if "validation_errors" in consolidated.columns:
        consolidated = consolidated.drop(columns=["validation_errors"])

    invalid_count = len(validation_errors)
    duplicate_count = len(duplicates)
    error_frames = [frame for frame in (validation_errors, duplicates) if not frame.empty]
    all_errors = (
        pd.concat(error_frames, ignore_index=True, sort=False)
        if error_frames
        else _empty_like(combined_valid)
    )



    summary_values = {
        "Files processed": files_succeeded,
        "Valid rows": len(consolidated),
        "Error rows": len(all_errors),
        "Duplicates removed": duplicate_count,
    }

    summary = pd.DataFrame({"Metric": list(summary_values.keys()), "Value": list(summary_values.values())})
    report_path, error_path, log_path = _write_outputs(
        output_dir, consolidated, all_errors, summary, log_lines
    )

    return ProcessingResult(
        files_processed=files_succeeded,
        valid_rows=len(consolidated),
        error_rows=len(all_errors),
        duplicates_removed=duplicate_count,
        report_path=report_path,
        error_path=error_path,
        log_path=log_path,
        worksheet_successes=tuple(worksheet_successes),
        worksheet_failures=tuple(worksheet_failures),
    )
