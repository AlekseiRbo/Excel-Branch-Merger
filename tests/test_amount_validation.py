from decimal import Decimal

import pandas as pd
import pytest

from src.excel_branch_merger.validators import parse_amount, validate_dataframe


@pytest.mark.parametrize(
    ("raw_amount", "expected"),
    [
        (1234, 1234.0),
        (1234.56, 1234.56),
        (1e3, 1000.0),
        (Decimal("1234.56"), 1234.56),
        ("1234", 1234.0),
        ("1234.56", 1234.56),
        ("1,234.56", 1234.56),
        (" 1234.56 ", 1234.56),
    ],
)
def test_parse_amount_accepts_supported_values(
    raw_amount: object,
    expected: float,
) -> None:
    assert parse_amount(raw_amount) == pytest.approx(expected)


@pytest.mark.parametrize(
    "raw_amount",
    [
        None,
        pd.NA,
        "",
        "   ",
        "1e3",
        "12abc34",
        "1.234,56",
        "1 234,56",
        "(1,200)",
        "$1,234.56",
        "12,34",
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        object(),
    ],
)
def test_parse_amount_rejects_unsupported_values(raw_amount: object) -> None:
    assert parse_amount(raw_amount) is None


@pytest.mark.parametrize("raw_amount", [0, -10, "0", "-10", "-1,200.50"])
def test_validate_dataframe_rejects_non_positive_amounts(
    raw_amount: object,
) -> None:
    dataframe = pd.DataFrame(
        {
            "customer_name": ["Alice"],
            "sale_date": ["2026-08-01"],
            "amount": [raw_amount],
        }
    )

    result = validate_dataframe(
        dataframe,
        required_fields=["customer_name", "sale_date", "amount"],
        date_formats=["%Y-%m-%d"],
    )

    assert result.valid_rows.empty
    assert "Amount must be greater than zero" in (
        result.error_rows.iloc[0]["validation_errors"]
    )


def test_invalid_amount_is_rejected_without_rewriting_original_value() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_name": ["Alice"],
            "sale_date": ["2026-08-01"],
            "amount": ["12abc34"],
        }
    )

    result = validate_dataframe(
        dataframe,
        required_fields=["customer_name", "sale_date", "amount"],
        date_formats=["%Y-%m-%d"],
    )

    assert result.valid_rows.empty
    assert len(result.error_rows) == 1
    assert result.error_rows.iloc[0]["validation_errors"] == (
        "Invalid amount: '12abc34'; expected a number such as "
        "1234.56 or 1,234.56"
    )
