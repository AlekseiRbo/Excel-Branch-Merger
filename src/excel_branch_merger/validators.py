from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from numbers import Real
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from pandas._libs.tslibs.nattype import NaTType


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

    if isinstance(value, Real):
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
) -> tuple[pd.Timestamp | NaTType, bool]:
    """Parse one date value and report whether it is ambiguous.

    A text value is ambiguous when two configured formats parse it into
    different calendar dates. For example, 08/04/2026 can mean either
    8 April or 4 August when both DMY and MDY formats are enabled.
    """
    if value is None or value is pd.NA:
        return pd.NaT, False

    if isinstance(value, (pd.Timestamp, datetime, date)):
        parsed_timestamp = pd.Timestamp(value)
        if pd.isna(parsed_timestamp):
            return pd.NaT, False
        return parsed_timestamp.normalize(), False

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


def _validate_legacy_dataframe(
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
        parsed_values: list[pd.Timestamp | NaTType] = []
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


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_missing_scalar(value: object) -> bool:
    if value is None or value is pd.NA or value is pd.NaT:
        return True

    if isinstance(value, Real):
        try:
            return math.isnan(float(value))
        except (TypeError, ValueError, OverflowError):
            return False

    return isinstance(value, str) and not value.strip()


def _validate_configured_dataframe(
    dataframe: pd.DataFrame,
    fields: dict[str, dict[str, Any]],
) -> ValidationResult:
    df = dataframe.copy()
    messages = [""] * len(df)

    for field_name, field_spec in fields.items():
        if field_name not in df.columns:
            df[field_name] = pd.NA

        field_type = field_spec.get("type", "text")
        required = bool(field_spec.get("required", False))

        raw_formats = field_spec.get("formats", [])
        configured_formats = (
            [item for item in raw_formats if isinstance(item, str)]
            if isinstance(raw_formats, list)
            else []
        )
        date_formats = list(dict.fromkeys(["%Y-%m-%d", *configured_formats]))

        values = df[field_name].tolist()

        for position, value in enumerate(values):
            is_missing = _is_missing_scalar(value)

            if required and is_missing:
                messages[position] += f"Missing required field: {field_name}; "
                continue

            if is_missing:
                continue

            if field_type == "email":
                text_value = str(value).strip()
                if _EMAIL_PATTERN.fullmatch(text_value) is None:
                    messages[position] += f"Invalid {field_name}; "

            elif field_type == "number":
                if parse_amount(value) is None:
                    messages[position] += f"Invalid {field_name}; "

            elif field_type == "date":
                parsed, is_ambiguous = parse_date_value(
                    value,
                    date_formats,
                )

                if is_ambiguous:
                    original_value = str(value).strip()
                    messages[position] += f"Ambiguous {field_name}: {original_value}; "
                elif pd.isna(parsed):
                    messages[position] += f"Invalid {field_name}; "

    error_messages = pd.Series(
        messages,
        index=df.index,
        dtype="string",
    ).str.rstrip("; ")

    df["validation_errors"] = error_messages

    error_mask = df["validation_errors"].ne("")

    return ValidationResult(
        valid_rows=df.loc[~error_mask].copy(),
        error_rows=df.loc[error_mask].copy(),
    )


def validate_dataframe(
    dataframe: pd.DataFrame,
    required_fields: Iterable[str],
    date_formats: list[str],
    *,
    fields: dict[str, dict[str, Any]] | None = None,
) -> ValidationResult:
    if fields:
        return _validate_configured_dataframe(
            dataframe,
            fields,
        )

    return _validate_legacy_dataframe(
        dataframe,
        required_fields,
        date_formats,
    )
