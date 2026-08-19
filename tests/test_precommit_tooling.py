import tomllib
from pathlib import Path


def load_pyproject() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def test_existing_quality_baselines_are_preserved() -> None:
    data = load_pyproject()

    ruff = data["tool"]["ruff"]["lint"]
    assert ruff["select"] == ["E4", "E7", "E9", "F", "I", "UP"]
    assert ruff["ignore"] == ["UP042"]

    mypy = data["tool"]["mypy"]
    assert mypy["python_version"] == "3.11"
    assert mypy["explicit_package_bases"] is True
    assert mypy["files"] == ["src", "gui.py", "main.py"]
    assert mypy["show_error_codes"] is True
    assert mypy["warn_unused_configs"] is True


def test_precommit_dependency_is_pinned() -> None:
    dev = load_pyproject()["dependency-groups"]["dev"]

    assert "pre-commit==4.6.0" in dev


def test_precommit_config_defines_quality_gates() -> None:
    text = Path(".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert 'minimum_pre_commit_version: "4.6.0"' in text

    assert "id: uv-lock" in text
    assert "entry: uv lock --check" in text

    assert "id: ruff-check" in text
    assert (
        "entry: uv run --locked ruff check gui.py main.py dev_runner.py src tests"
    ) in text

    assert "id: ruff-format" in text
    assert (
        "entry: uv run --locked ruff format --check "
        "gui.py main.py dev_runner.py src tests"
    ) in text


def test_precommit_mypy_uses_python_311() -> None:
    text = Path(".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "id: mypy" in text
    assert ("entry: uv run --isolated --locked --python 3.11 mypy") in text

    assert text.count("pass_filenames: false") == 4
    assert text.count("always_run: true") == 4


def test_readme_documents_precommit_workflow() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## Pre-commit hooks" in text
    assert "uv run --locked pre-commit install" in text
    assert "uv run --locked pre-commit run --all-files" in text
