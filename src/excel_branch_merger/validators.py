from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class ValidationResult:
    valid_rows: pd.DataFrame
    error_rows: pd.DataFrame


def normalize_header(value: object) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def build_alias_lookup(canonical_columns: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}

    for canonical_name, aliases in canonical_columns.items():
        lookup[normalize_header(canonical_name)] = canonical_name
        for alias in aliases:
            normalized_alias = normalize_header(alias)
            existing = lookup.get(normalized_alias)
            if existing and existing != canonical_name:
                raise ValueError(
                    f"Alias '{alias}' is assigned to both "
                    f"'{existing}' and '{canonical_name}'."
                )
            lookup[normalized_alias] = canonical_name

    return lookup


def normalize_columns(
    dataframe: pd.DataFrame,
    canonical_columns: dict[str, list[str]],
) -> pd.DataFrame:
    alias_lookup = build_alias_lookup(canonical_columns)
    rename_map: dict[object, str] = {}

    for column in dataframe.columns:
        normalized = normalize_header(column)
        if normalized in alias_lookup:
            rename_map[column] = alias_lookup[normalized]

    normalized_df = dataframe.rename(columns=rename_map).copy()

    duplicate_column_names = normalized_df.columns[
        normalized_df.columns.duplicated()
    ].tolist()
    if duplicate_column_names:
        raise ValueError(
            "Multiple input columns map to the same canonical field: "
            f"{duplicate_column_names}"
        )

    return normalized_df


def parse_date_value(
    value: object,
    date_formats: list[str],
) -> tuple[pd.Timestamp | pd.NaT, bool]:
    """Parse one date value and report whether it is ambiguous.

    A text value is ambiguous when two configured formats parse it into
    different calendar dates. For example, 08/04/2026 can mean either
    8 April or 4 August when both DMY and MDY formats are enabled.
    """
    if value is None or value is pd.NA:
        return pd.NaT, False

    if isinstance(value, (pd.Timestamp, datetime, date)):
        parsed = pd.Timestamp(value)
        if pd.isna(parsed):
            return pd.NaT, False
        return parsed.normalize(), False

    text = str(value).strip()
    if not text:
        return pd.NaT, False

    candidates: dict[int, pd.Timestamp] = {}
    for date_format in date_formats:
        parsed = pd.to_datetime(text, format=date_format, errors="coerce")
        if pd.isna(parsed):
            continue
        timestamp = pd.Timestamp(parsed).normalize()
        candidates[timestamp.value] = timestamp

    if len(candidates) == 1:
        return next(iter(candidates.values())), False

    if len(candidates) > 1:
        return pd.NaT, True

    return pd.NaT, False


def validate_dataframe(
    dataframe: pd.DataFrame,
    required_fields: Iterable[str],
    date_formats: list[str],
) -> ValidationResult:
    df = dataframe.copy()

    required_fields = list(required_fields)
    for field in required_fields:
        if field not in df.columns:
            df[field] = pd.NA

    required_missing_masks: dict[str, pd.Series] = {}
    for field in required_fields:
        original_field = df[field]
        missing = original_field.isna()
        if (
            original_field.dtype == "object"
            or str(original_field.dtype).startswith("string")
        ):
            missing = missing | original_field.astype("string").str.strip().eq("")
        required_missing_masks[field] = missing

    ambiguous_dates = pd.Series(False, index=df.index, dtype="bool")
    original_dates = pd.Series(pd.NA, index=df.index, dtype="object")

    if "sale_date" in df.columns:
        original_dates = df["sale_date"].copy()
        parsed_values: list[pd.Timestamp | pd.NaT] = []
        ambiguous_values: list[bool] = []

        for value in original_dates:
            parsed, is_ambiguous = parse_date_value(value, date_formats)
            parsed_values.append(parsed)
            ambiguous_values.append(is_ambiguous)

        df["sale_date"] = pd.Series(
            parsed_values,
            index=df.index,
            dtype="datetime64[ns]",
        )
        ambiguous_dates = pd.Series(
            ambiguous_values,
            index=df.index,
            dtype="bool",
        )

    if "amount" in df.columns:
        cleaned_amount = (
            df["amount"]
            .astype("string")
            .str.replace(",", "", regex=False)
            .str.replace(r"[^\d.\-]", "", regex=True)
        )
        df["amount"] = pd.to_numeric(cleaned_amount, errors="coerce")

    error_messages = pd.Series("", index=df.index, dtype="string")

    for field in required_fields:
        error_messages.loc[required_missing_masks[field]] += (
            f"Missing required field: {field}; "
        )

    if "sale_date" in df.columns:
        invalid_dates = df["sale_date"].isna() & ~ambiguous_dates
        error_messages.loc[invalid_dates] += "Invalid sale_date; "

        for row_index in df.index[ambiguous_dates]:
            original_value = str(original_dates.loc[row_index]).strip()
            error_messages.loc[row_index] += (
                f"Ambiguous sale_date: {original_value}; use YYYY-MM-DD; "
            )

    if "amount" in df.columns:
        invalid_amounts = df["amount"].isna()
        non_positive_amounts = df["amount"].notna() & (df["amount"] <= 0)
        error_messages.loc[invalid_amounts] += "Invalid amount; "
        error_messages.loc[non_positive_amounts] += "Amount must be greater than zero; "

    df["validation_errors"] = error_messages.str.rstrip("; ")

    error_mask = df["validation_errors"].ne("")
    return ValidationResult(
        valid_rows=df.loc[~error_mask].copy(),
        error_rows=df.loc[error_mask].copy(),
    )
