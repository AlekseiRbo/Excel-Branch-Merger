from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

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
