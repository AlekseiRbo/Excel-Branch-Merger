import tomllib
from pathlib import Path


def load_pyproject() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def test_mypy_dependencies_are_pinned() -> None:
    data = load_pyproject()
    dev = data["dependency-groups"]["dev"]

    assert "mypy==2.3.0" in dev
    assert "pandas-stubs==2.3.3.260113" in dev
    assert "types-openpyxl==3.1.5.20260807" in dev


def test_existing_ruff_baseline_is_preserved() -> None:
    data = load_pyproject()
    lint = data["tool"]["ruff"]["lint"]

    assert lint["select"] == ["E4", "E7", "E9", "F", "I", "UP"]
    assert lint["ignore"] == ["UP042"]


def test_mypy_configuration_has_stable_baseline() -> None:
    config = load_pyproject()["tool"]["mypy"]

    assert config["python_version"] == "3.11"
    assert config["explicit_package_bases"] is True
    assert config["files"] == ["src", "gui.py", "main.py"]
    assert config["show_error_codes"] is True
    assert config["warn_unused_configs"] is True

    assert "ignore_missing_imports" not in config


def test_ci_runs_mypy_on_python_311() -> None:
    text = Path(".github/workflows/tests.yml").read_text(encoding="utf-8")

    assert "Type check on Python 3.11" in text
    assert "uv sync --locked --python 3.11" in text
    assert ".venv-mypy311" in text
    assert "python.exe -m mypy" in text


def test_readme_documents_mypy() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## Type checking" in text
    assert "uv sync --locked --python 3.11" in text
    assert ".venv-mypy311" in text
    assert "python.exe -m mypy" in text
