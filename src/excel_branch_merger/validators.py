from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from numbers import Number

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


_AMOUNT_PATTERN = re.compile(
    r"-?(?:[0-9]+(?:\.[0-9]+)?|[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?)"
)


def parse_amount(value: object) -> float | None:
    """Parse a supported amount without rewriting unknown characters.

    Accepted text formats are plain decimal numbers (``1234.56``) and
    comma-grouped thousands (``1,234.56``), with optional surrounding
    whitespace and an optional leading minus sign. Numeric cell values are
    accepted when finite. Unsupported or non-finite values return ``None``.
    Positivity is validated separately as a business rule.
    """
    if value is None or value is pd.NA or isinstance(value, bool):
        return None

    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        try:
            numeric_value = float(value)
        except (OverflowError, ValueError):
            return None
        return numeric_value if math.isfinite(numeric_value) else None

    if isinstance(value, Number):
        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return numeric_value if math.isfinite(numeric_value) else None

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text or _AMOUNT_PATTERN.fullmatch(text) is None:
        return None

    try:
        decimal_value = Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None

    if not decimal_value.is_finite():
        return None

    try:
        numeric_value = float(decimal_value)
    except (OverflowError, ValueError):
        return None
    return numeric_value if math.isfinite(numeric_value) else None


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
        if original_field.dtype == "object" or str(original_field.dtype).startswith(
            "string"
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

    original_amounts = pd.Series(pd.NA, index=df.index, dtype="object")
    if "amount" in df.columns:
        original_amounts = df["amount"].copy()
        parsed_amounts = [parse_amount(value) for value in original_amounts]
        df["amount"] = pd.Series(parsed_amounts, index=df.index, dtype="float64")

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
        for row_index in df.index[invalid_amounts]:
            original_value = original_amounts.loc[row_index]
            error_messages.loc[row_index] += (
                f"Invalid amount: {original_value!r}; expected a number such as "
                "1234.56 or 1,234.56; "
            )
        error_messages.loc[non_positive_amounts] += "Amount must be greater than zero; "

    df["validation_errors"] = error_messages.str.rstrip("; ")

    error_mask = df["validation_errors"].ne("")
    return ValidationResult(
        valid_rows=df.loc[~error_mask].copy(),
        error_rows=df.loc[error_mask].copy(),
    )
