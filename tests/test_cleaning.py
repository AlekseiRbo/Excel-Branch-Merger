import pandas as pd

from src.excel_branch_merger.cleaning import clean_dataframe

FIELDS = {
    "customer_name": {
        "aliases": ["Customer"],
        "required": True,
        "type": "text",
        "case": "preserve",
    },
    "email": {
        "aliases": ["Email"],
        "required": True,
        "type": "email",
        "case": "lower",
    },
    "amount": {
        "aliases": ["Amount"],
        "type": "number",
        "case": "preserve",
    },
    "sale_date": {
        "aliases": ["Date"],
        "type": "date",
        "case": "preserve",
        "formats": [
            "%Y-%m-%d",
            "%d/%m/%Y",
        ],
    },
}


def test_text_whitespace_is_trimmed_and_collapsed() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_name": [
                "   Alpha     Trading   Company   ",
            ]
        }
    )

    result = clean_dataframe(
        dataframe,
        fields=FIELDS,
        missing_values=["", "N/A", "NA", "null"],
    )

    assert result.loc[0, "customer_name"] == "Alpha Trading Company"


def test_configured_missing_markers_become_missing_values() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_name": [" N/A "],
            "email": ["null"],
            "amount": ["NA"],
        }
    )

    result = clean_dataframe(
        dataframe,
        fields=FIELDS,
        missing_values=["", "N/A", "NA", "null"],
    )

    assert pd.isna(result.loc[0, "customer_name"])
    assert pd.isna(result.loc[0, "email"])
    assert pd.isna(result.loc[0, "amount"])


def test_email_is_trimmed_and_lowercased() -> None:
    dataframe = pd.DataFrame(
        {
            "email": [
                "  Sales.Team@Example.COM  ",
            ]
        }
    )

    result = clean_dataframe(
        dataframe,
        fields=FIELDS,
        missing_values=["", "N/A", "NA", "null"],
    )

    assert result.loc[0, "email"] == "sales.team@example.com"


def test_number_is_normalized_without_guessing_unknown_formats() -> None:
    dataframe = pd.DataFrame(
        {
            "amount": [
                " 1,250.50 ",
                "invalid-number",
            ]
        }
    )

    result = clean_dataframe(
        dataframe,
        fields=FIELDS,
        missing_values=["", "N/A", "NA", "null"],
    )

    assert result.loc[0, "amount"] == 1250.50
    assert result.loc[1, "amount"] == "invalid-number"


def test_date_is_normalized_to_iso_when_unambiguous() -> None:
    dataframe = pd.DataFrame(
        {
            "sale_date": [
                "2026-08-20",
                "21/08/2026",
            ]
        }
    )

    result = clean_dataframe(
        dataframe,
        fields=FIELDS,
        missing_values=["", "N/A", "NA", "null"],
    )

    assert result["sale_date"].tolist() == [
        "2026-08-20",
        "2026-08-21",
    ]


def test_ambiguous_date_is_not_guessed() -> None:
    fields = {
        **FIELDS,
        "sale_date": {
            **FIELDS["sale_date"],
            "formats": [
                "%d/%m/%Y",
                "%m/%d/%Y",
            ],
        },
    }

    dataframe = pd.DataFrame(
        {
            "sale_date": [
                "08/04/2026",
            ]
        }
    )

    result = clean_dataframe(
        dataframe,
        fields=fields,
        missing_values=["", "N/A", "NA", "null"],
    )

    assert result.loc[0, "sale_date"] == "08/04/2026"


def test_field_case_policy_supports_preserve_lower_and_upper() -> None:
    fields = {
        "preserved": {
            "aliases": [],
            "type": "text",
            "case": "preserve",
        },
        "lowered": {
            "aliases": [],
            "type": "text",
            "case": "lower",
        },
        "uppered": {
            "aliases": [],
            "type": "text",
            "case": "upper",
        },
    }

    dataframe = pd.DataFrame(
        {
            "preserved": ["  Acme Corp  "],
            "lowered": ["  Acme Corp  "],
            "uppered": ["  Acme Corp  "],
        }
    )

    result = clean_dataframe(
        dataframe,
        fields=fields,
        missing_values=[""],
    )

    assert result.loc[0, "preserved"] == "Acme Corp"
    assert result.loc[0, "lowered"] == "acme corp"
    assert result.loc[0, "uppered"] == "ACME CORP"
