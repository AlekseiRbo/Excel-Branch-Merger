# Excel Branch Merger

[![tests](https://github.com/AlekseiRbo/Excel-Branch-Merger/actions/workflows/tests.yml/badge.svg)](https://github.com/AlekseiRbo/Excel-Branch-Merger/actions/workflows/tests.yml)

A desktop Python application for consolidating, cleaning, validating, and deduplicating spreadsheet data from Excel and CSV files.

![Excel Branch Merger](screenshots/application.png)

## Features

- Processes `.xlsx` and `.csv` files from one input folder
- Reads all non-empty Excel worksheets
- Supports mixed Excel and CSV input in one run
- Maps source columns to configurable canonical fields
- Cleans whitespace, missing values, case, numbers, and dates before validation
- Validates required fields, email addresses, numbers, and deterministic date formats
- Removes duplicates using configurable single or composite keys
- Preserves `source_file`, `source_sheet`, and `source_row` lineage
- Generates consolidated data, rejected rows, summary metrics, and a processing log
- Runs file processing in a background thread to keep the GUI responsive
- Lets the GUI user select a YAML, YML, or legacy JSON configuration
- Retains legacy `config.json` support

## Supported input

v1.4 supports:

- `.xlsx`
- `.csv`

The processing engine does not support legacy `.xls`, PDF, Google Sheets, databases, or APIs.

CSV encoding and delimiter are configured in `processing.yaml`.

## Technology

- Python
- Tkinter
- pandas
- openpyxl
- PyYAML
- Pillow
- pytest
- Ruff
- mypy
- pre-commit
- uv

## Project structure

```text
excel_branch_merger/
├── assets/
├── demo/
│   └── v1.4/
│       ├── input/
│       │   ├── north.xlsx
│       │   └── south.csv
│       └── processing.yaml
├── screenshots/
├── src/excel_branch_merger/
│   ├── cleaning.py
│   ├── config.py
│   ├── merger.py
│   ├── validators.py
│   └── version.py
├── tests/
├── config.json
├── gui.py
├── main.py
├── dev_runner.py
├── pyproject.toml
└── uv.lock
```

## Installation

Install dependencies with uv:

```powershell
uv sync --locked
```

## Running the application

Run the GUI through the project environment:

```powershell
uv run --locked python gui.py
```

The Windows launcher can also be used:

```text
START_GUI.bat
```

The GUI lets you choose:

1. Input folder
2. Output folder
3. Configuration file

For v1.4, select a `processing.yaml` or `processing.yml` file.

If `processing.yaml` exists in the application directory, the GUI prefers it automatically. Otherwise it falls back to `processing.yml`, then legacy `config.json`.

## v1.4 configuration

The recommended configuration format is YAML.

A complete working example is included at:

```text
demo/v1.4/processing.yaml
```

The configuration controls:

- CSV encoding and delimiter
- column aliases
- required fields
- field types: `text`, `email`, `number`, `date`
- case normalization
- deterministic date formats
- missing-value markers
- deduplication keys
- source lineage export

## Column mapping

Each canonical field can define aliases. Matching is case-insensitive after header normalization, and the canonical field name itself is also accepted.

`input.unmapped_columns` supports:

- `preserve`
- `drop`

If multiple source columns map to the same canonical field, the source is rejected explicitly instead of guessing.

## Cleaning and validation

Cleaning runs before validation and deduplication.

The pipeline can:

- trim and collapse whitespace
- convert configured missing markers to missing values
- apply `preserve`, `lower`, or `upper` case policies
- normalize supported numeric values
- normalize deterministic configured dates to ISO `YYYY-MM-DD`

Supported field types are:

- `text`
- `email`
- `number`
- `date`

Any configured field can use `required: true`.

Ambiguous dates are not guessed. Invalid rows are written to `Errors.xlsx`.

## Deduplication

Deduplication runs after cleaning and validation.

Example:

```yaml
deduplication:
  keys:
    - email
    - invoice_date
  keep: first
```

Rows with incomplete deduplication keys are kept and excluded from duplicate comparison. They are reported separately as `Incomplete dedup key rows`.

`keep: first` is deterministic because input files are processed in sorted order.

## Source lineage

When enabled:

```yaml
output:
  include_source_lineage: true
```

exports contain:

- `source_file`
- `source_sheet`
- `source_row`

For CSV files, `source_sheet` is `CSV`.

Lineage may be hidden from exported workbooks with `include_source_lineage: false`; it remains available internally during processing.

## v1.4 output

The v1.4 profile creates:

```text
Consolidated.xlsx
Errors.xlsx
processing.log
```

`Consolidated.xlsx` contains:

- `Data`
- `Summary`

`Errors.xlsx` contains invalid rows and removed duplicate rows.

`processing.log` contains per-source events, summary metrics, row invariant information, generated output names, and the final processing status.

## Processing metrics

The summary includes:

- Files discovered
- Files succeeded
- Files failed
- Worksheets succeeded
- Worksheets failed
- Total input rows
- Valid rows
- Invalid rows
- Duplicate rows
- Incomplete dedup key rows
- Total rejected rows

For normal row-level processing:

```text
Total input rows = Valid rows + Invalid rows + Duplicate rows
```

File-level read failures are reported separately.

## Demo dataset

A ready-to-run v1.4 example is included in:

```text
demo/v1.4/
├── processing.yaml
└── input/
    ├── north.xlsx
    └── south.csv
```

Expected result:

```text
Status: COMPLETED_WITH_WARNINGS
Files discovered: 2
Total input rows: 6
Valid rows: 4
Invalid rows: 1
Duplicate rows: 1
Incomplete dedup key rows: 1
```

To run it in the GUI:

1. Select `demo/v1.4/input` as the input folder
2. Select a separate output folder
3. Select `demo/v1.4/processing.yaml` as the configuration file
4. Click `Process Excel Files`

## Legacy console mode

The existing console entry point remains available:

```powershell
python main.py
```

It continues to use the repository `input` and `output` folders together with legacy `config.json`.

## Portfolio screenshot

Generate an updated application screenshot after changing the interface or icons:

```powershell
python make_screenshot.py
```

The script processes the bundled sample workbooks, displays completed metrics, replaces personal absolute paths with `\.\input` and `\.\output`, and saves the result to:

```text
screenshots/application.png
```

On Windows, `MAKE_SCREENSHOT.bat` runs the same workflow.

## Development

Run the automated tests:

```powershell
python -m pytest -q
```

Start the interface with automatic restart after source or asset changes:

```powershell
python dev_runner.py
```

## Code quality

Run Ruff lint checks:

`uv run --locked ruff check gui.py main.py dev_runner.py src tests`

Check formatting:

`uv run --locked ruff format --check gui.py main.py dev_runner.py src tests`

## Type checking

Create or update the dedicated Python 3.11 type-check environment:

`$env:UV_PROJECT_ENVIRONMENT = ".venv-mypy311"; uv sync --locked --python 3.11`

Run mypy:

`.\.venv-mypy311\Scripts\python.exe -m mypy`

Afterwards, clear the temporary project-environment override:

`Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue`

## Pre-commit hooks

Install the repository hooks:

`uv run --locked pre-commit install`

Run all configured hooks manually:

`uv run --locked pre-commit run --all-files`

## Test coverage

Run the core-package coverage gate:

`uv run --locked python -m pytest -q --cov=src/excel_branch_merger`

The project enforces branch coverage with a minimum total coverage of 80%.

## License

MIT License. See `LICENSE`.
