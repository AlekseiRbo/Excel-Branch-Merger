from __future__ import annotations

from typing import Any

import pandas as pd

from .validators import parse_amount, parse_date_value


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _missing_lookup(missing_values: list[str]) -> set[str]:
    return {_normalize_text(value).casefold() for value in missing_values}


def _clean_scalar(
    value: object,
    *,
    field_spec: dict[str, Any],
    missing_lookup: set[str],
) -> object:
    if value is None or value is pd.NA:
        return pd.NA

    cleaned: object = value

    if isinstance(cleaned, str):
        text = _normalize_text(cleaned)

        if text.casefold() in missing_lookup:
            return pd.NA

        cleaned = text

    field_type = field_spec.get("type", "text")

    if field_type == "number":
        parsed_number = parse_amount(cleaned)
        if parsed_number is not None:
            return parsed_number
        return cleaned

    if field_type == "date":
        formats = field_spec.get("formats", [])
        if isinstance(formats, list) and formats:
            parsed_date, is_ambiguous = parse_date_value(
                cleaned,
                formats,
            )
            if not is_ambiguous and not pd.isna(parsed_date):
                return pd.Timestamp(parsed_date).strftime("%Y-%m-%d")
        return cleaned

    case_policy = field_spec.get("case", "preserve")

    if isinstance(cleaned, str):
        if case_policy == "lower":
            return cleaned.lower()
        if case_policy == "upper":
            return cleaned.upper()

    return cleaned


def clean_dataframe(
    dataframe: pd.DataFrame,
    *,
    fields: dict[str, dict[str, Any]],
    missing_values: list[str],
) -> pd.DataFrame:
    cleaned = dataframe.copy()
    missing_lookup = _missing_lookup(missing_values)

    for field_name, field_spec in fields.items():
        if field_name not in cleaned.columns:
            continue

        cleaned[field_name] = cleaned[field_name].map(
            lambda value: _clean_scalar(
                value,
                field_spec=field_spec,
                missing_lookup=missing_lookup,
            )
        )

    return cleaned
