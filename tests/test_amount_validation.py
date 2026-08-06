import pandas as pd
import pytest

from src.excel_branch_merger.validators import validate_dataframe


@pytest.mark.parametrize(
    "raw_amount",
    ["1e3", "12abc34", "1.234,56", "(1,200)"],
)
def test_malformed_amount_is_rejected_without_rewriting(
    raw_amount: str,
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
    assert len(result.error_rows) == 1
