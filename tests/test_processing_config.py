from pathlib import Path

import pytest

from src.excel_branch_merger.config import load_config

VALID_CONFIG = """\
input:
  csv:
    encoding: utf-8-sig
    delimiter: ","
  unmapped_columns: preserve

fields:
  customer_name:
    aliases:
      - Customer Name
      - Customer
    required: true
    type: text
    case: preserve

  email:
    aliases:
      - Email
      - E-mail
    required: true
    type: email
    case: lower

  amount:
    aliases:
      - Amount
      - Total
    type: number

  invoice_date:
    aliases:
      - Date
      - Invoice Date
    type: date
    formats:
      - "%Y-%m-%d"
      - "%d/%m/%Y"

deduplication:
  keys:
    - email
  keep: first

missing_values:
  - ""
  - "N/A"
  - "NA"
  - "null"

output:
  include_source_lineage: true
"""


def write_config(tmp_path: Path, text: str = VALID_CONFIG) -> Path:
    path = tmp_path / "processing.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_processing_yaml_contract(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path))

    assert config["input"]["csv"]["encoding"] == "utf-8-sig"
    assert config["input"]["csv"]["delimiter"] == ","
    assert config["input"]["unmapped_columns"] == "preserve"

    assert config["fields"]["customer_name"]["required"] is True
    assert config["fields"]["email"]["type"] == "email"
    assert config["fields"]["email"]["case"] == "lower"

    assert config["fields"]["invoice_date"]["formats"] == [
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]

    assert config["deduplication"] == {
        "keys": ["email"],
        "keep": "first",
    }

    assert config["output"]["include_source_lineage"] is True


def test_rejects_alias_owned_by_multiple_fields(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """\
fields:
  customer_name:
    aliases: [Customer]
  email:
    aliases: [customer]
deduplication:
  keys: []
  keep: first
""",
    )

    with pytest.raises(ValueError, match="alias"):
        load_config(path)


def test_rejects_unknown_deduplication_key(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """\
fields:
  email:
    aliases: [Email]
deduplication:
  keys: [customer_name]
  keep: first
""",
    )

    with pytest.raises(ValueError, match="dedup"):
        load_config(path)


def test_rejects_unknown_field_type(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """\
fields:
  amount:
    aliases: [Amount]
    type: currency_magic
deduplication:
  keys: []
  keep: first
""",
    )

    with pytest.raises(ValueError, match="type"):
        load_config(path)


def test_rejects_invalid_unmapped_columns_policy(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """\
input:
  unmapped_columns: guess
fields:
  email:
    aliases: [Email]
deduplication:
  keys: []
  keep: first
""",
    )

    with pytest.raises(ValueError, match="unmapped"):
        load_config(path)
