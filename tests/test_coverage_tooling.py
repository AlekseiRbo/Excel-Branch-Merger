import tomllib
from pathlib import Path


def load_pyproject() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def test_existing_quality_baselines_are_preserved() -> None:
    data = load_pyproject()
    dev = data["dependency-groups"]["dev"]

    assert "mypy==2.3.0" in dev
    assert "pre-commit==4.6.0" in dev
    assert "ruff==0.16.0" in dev

    ruff = data["tool"]["ruff"]["lint"]
    assert ruff["select"] == ["E4", "E7", "E9", "F", "I", "UP"]
    assert ruff["ignore"] == ["UP042"]

    mypy = data["tool"]["mypy"]
    assert mypy["python_version"] == "3.11"
    assert mypy["explicit_package_bases"] is True
    assert mypy["files"] == ["src", "gui.py", "main.py"]
    assert mypy["show_error_codes"] is True
    assert mypy["warn_unused_configs"] is True


def test_coverage_dependencies_are_pinned() -> None:
    dev = load_pyproject()["dependency-groups"]["dev"]

    assert "coverage==7.15.2" in dev
    assert "pytest-cov==7.1.0" in dev


def test_coverage_has_stable_core_baseline() -> None:
    data = load_pyproject()

    run = data["tool"]["coverage"]["run"]
    report = data["tool"]["coverage"]["report"]

    assert run["branch"] is True
    assert run["source"] == ["src/excel_branch_merger"]

    assert report["show_missing"] is True
    assert report["precision"] == 2
    assert report["fail_under"] == 80


def test_ci_enforces_coverage_gate() -> None:
    text = Path(".github/workflows/tests.yml").read_text(encoding="utf-8")

    assert "Run tests with coverage" in text
    assert ("uv run --locked python -m pytest -q --cov=src/excel_branch_merger") in text


def test_readme_documents_coverage_gate() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## Test coverage" in text
    assert ("uv run --locked python -m pytest -q --cov=src/excel_branch_merger") in text
    assert "minimum total coverage of 80%" in text
