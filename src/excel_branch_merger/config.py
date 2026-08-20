from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

_SUPPORTED_FIELD_TYPES = {"text", "email", "number", "date"}
_SUPPORTED_CASE_POLICIES = {"preserve", "lower", "upper"}
_SUPPORTED_UNMAPPED_POLICIES = {"preserve", "drop"}


def _normalized_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _load_legacy_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("Configuration root must be an object.")

    required_sections = {
        "canonical_columns",
        "required_fields",
        "duplicate_key",
        "date_formats",
    }
    missing = required_sections - set(config)
    if missing:
        raise ValueError(f"Missing configuration sections: {sorted(missing)}")

    return config


def _validate_fields(raw_fields: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_fields, dict) or not raw_fields:
        raise ValueError("fields must be a non-empty mapping.")

    fields: dict[str, dict[str, Any]] = {}
    alias_owners: dict[str, str] = {}

    for canonical_name, raw_spec in raw_fields.items():
        if not isinstance(canonical_name, str) or not canonical_name.strip():
            raise ValueError("field names must be non-empty strings.")
        if not isinstance(raw_spec, dict):
            raise ValueError(
                f"field '{canonical_name}' configuration must be a mapping."
            )

        aliases = raw_spec.get("aliases", [])
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            raise ValueError(
                f"aliases for field '{canonical_name}' must be a list "
                "of non-empty strings."
            )

        required = raw_spec.get("required", False)
        if not isinstance(required, bool):
            raise ValueError(f"required for field '{canonical_name}' must be boolean.")

        field_type = raw_spec.get("type", "text")
        if field_type not in _SUPPORTED_FIELD_TYPES:
            raise ValueError(f"unknown field type for '{canonical_name}': {field_type}")

        case_policy = raw_spec.get("case", "preserve")
        if case_policy not in _SUPPORTED_CASE_POLICIES:
            raise ValueError(
                f"unknown case policy for field '{canonical_name}': {case_policy}"
            )

        formats = raw_spec.get("formats")
        if field_type == "date":
            if (
                not isinstance(formats, list)
                or not formats
                or not all(isinstance(item, str) and item.strip() for item in formats)
            ):
                raise ValueError(
                    f"date field '{canonical_name}' must define deterministic formats."
                )
        elif formats is not None:
            raise ValueError(
                f"formats are only valid for date field type: {canonical_name}"
            )

        names_to_claim = [canonical_name, *aliases]
        for source_name in names_to_claim:
            normalized = _normalized_name(source_name)
            owner = alias_owners.get(normalized)

            if owner is not None and owner != canonical_name:
                raise ValueError(
                    f"alias collision: '{source_name}' belongs to both "
                    f"'{owner}' and '{canonical_name}'."
                )

            alias_owners[normalized] = canonical_name

        field_spec: dict[str, Any] = {
            "aliases": list(aliases),
            "required": required,
            "type": field_type,
            "case": case_policy,
        }
        if formats is not None:
            field_spec["formats"] = list(formats)

        fields[canonical_name] = field_spec

    return fields


def _validate_processing_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("processing configuration root must be a mapping.")

    fields = _validate_fields(config.get("fields"))

    raw_input = config.get("input", {})
    if not isinstance(raw_input, dict):
        raise ValueError("input must be a mapping.")

    unmapped_columns = raw_input.get("unmapped_columns", "preserve")
    if unmapped_columns not in _SUPPORTED_UNMAPPED_POLICIES:
        raise ValueError("unmapped_columns must be either 'preserve' or 'drop'.")

    raw_csv = raw_input.get("csv", {})
    if not isinstance(raw_csv, dict):
        raise ValueError("input.csv must be a mapping.")

    encoding = raw_csv.get("encoding", "utf-8-sig")
    delimiter = raw_csv.get("delimiter", ",")

    if not isinstance(encoding, str) or not encoding.strip():
        raise ValueError("CSV encoding must be a non-empty string.")

    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ValueError("CSV delimiter must be exactly one character.")

    raw_dedup = config.get("deduplication", {})
    if not isinstance(raw_dedup, dict):
        raise ValueError("deduplication must be a mapping.")

    dedup_keys = raw_dedup.get("keys", [])
    if not isinstance(dedup_keys, list) or not all(
        isinstance(key, str) and key.strip() for key in dedup_keys
    ):
        raise ValueError("deduplication keys must be a list of field names.")

    unknown_dedup_keys = [key for key in dedup_keys if key not in fields]
    if unknown_dedup_keys:
        raise ValueError(
            f"deduplication keys reference undefined fields: {unknown_dedup_keys}"
        )

    keep = raw_dedup.get("keep", "first")
    if keep != "first":
        raise ValueError("deduplication keep currently supports only 'first'.")

    missing_values = config.get(
        "missing_values",
        ["", "N/A", "NA", "null"],
    )
    if not isinstance(missing_values, list) or not all(
        isinstance(value, str) for value in missing_values
    ):
        raise ValueError("missing_values must be a list of strings.")

    raw_output = config.get("output", {})
    if not isinstance(raw_output, dict):
        raise ValueError("output must be a mapping.")

    include_source_lineage = raw_output.get(
        "include_source_lineage",
        True,
    )
    if not isinstance(include_source_lineage, bool):
        raise ValueError("output.include_source_lineage must be boolean.")

    return {
        "input": {
            "csv": {
                "encoding": encoding,
                "delimiter": delimiter,
            },
            "unmapped_columns": unmapped_columns,
        },
        "fields": fields,
        "deduplication": {
            "keys": list(dedup_keys),
            "keep": keep,
        },
        "missing_values": list(missing_values),
        "output": {
            "include_source_lineage": include_source_lineage,
        },
    }


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    suffix = path.suffix.casefold()

    if suffix == ".json":
        return _load_legacy_json(path)

    if suffix not in {".yaml", ".yml"}:
        raise ValueError("Configuration file must use .yaml, .yml, or legacy .json.")

    try:
        with path.open("r", encoding="utf-8") as file:
            raw_config = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML configuration: {exc}") from exc

    return _validate_processing_config(raw_config)
