from datetime import datetime

import pandas as pd

from src.excel_branch_merger.validators import (
    normalize_columns,
    parse_date_value,
    validate_dataframe,
)


def test_normalize_columns_maps_aliases() -> None:
    dataframe = pd.DataFrame(
        {
            "Client": ["Alice"],
            "Order Date": ["2026-08-01"],
            "Total": [100],
        }
    )
    canonical_columns = {
        "customer_name": ["client", "customer"],
        "sale_date": ["order date", "date"],
        "amount": ["total", "revenue"],
    }

    result = normalize_columns(dataframe, canonical_columns)

    assert list(result.columns) == [
        "customer_name",
        "sale_date",
        "amount",
    ]


def test_validate_dataframe_separates_invalid_rows() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_name": ["Alice", ""],
            "sale_date": ["2026-08-01", "not-a-date"],
            "amount": [100, -5],
        }
    )

    result = validate_dataframe(
        dataframe,
        required_fields=["customer_name", "sale_date", "amount"],
        date_formats=["%Y-%m-%d"],
    )

    assert len(result.valid_rows) == 1
    assert len(result.error_rows) == 1
    assert "Missing required field: customer_name" in (
        result.error_rows.iloc[0]["validation_errors"]
    )
    assert "Invalid sale_date" in (
        result.error_rows.iloc[0]["validation_errors"]
    )
    assert "Amount must be greater than zero" in (
        result.error_rows.iloc[0]["validation_errors"]
    )


def test_parse_date_value_accepts_unambiguous_dates() -> None:
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]

    iso_date, iso_ambiguous = parse_date_value("2026-08-04", formats)
    dmy_date, dmy_ambiguous = parse_date_value("13/08/2026", formats)
    native_date, native_ambiguous = parse_date_value(
        datetime(2026, 8, 14),
        formats,
    )

    assert iso_date == pd.Timestamp("2026-08-04")
    assert dmy_date == pd.Timestamp("2026-08-13")
    assert native_date == pd.Timestamp("2026-08-14")
    assert not iso_ambiguous
    assert not dmy_ambiguous
    assert not native_ambiguous


def test_same_calendar_date_is_not_ambiguous() -> None:
    parsed, is_ambiguous = parse_date_value(
        "01/01/2026",
        ["%d/%m/%Y", "%m/%d/%Y"],
    )

    assert parsed == pd.Timestamp("2026-01-01")
    assert not is_ambiguous


def test_ambiguous_date_is_sent_to_error_report() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_name": ["Delta Shop"],
            "sale_date": ["08/04/2026"],
            "amount": [1700.50],
        }
    )

    result = validate_dataframe(
        dataframe,
        required_fields=["customer_name", "sale_date", "amount"],
        date_formats=["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"],
    )

    assert result.valid_rows.empty
    assert len(result.error_rows) == 1
    assert result.error_rows.iloc[0]["validation_errors"] == (
        "Ambiguous sale_date: 08/04/2026; use YYYY-MM-DD"
    )
