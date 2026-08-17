from pathlib import Path
import tomllib


TARGETS = "gui.py main.py dev_runner.py src tests"


def load_pyproject() -> dict:
    return tomllib.loads(
        Path("pyproject.toml").read_text(encoding="utf-8")
    )


def test_ruff_is_pinned_as_development_dependency() -> None:
    data = load_pyproject()

    assert "ruff==0.16.0" in data["dependency-groups"]["dev"]


def test_ruff_has_explicit_stable_configuration() -> None:
    data = load_pyproject()

    assert data["tool"]["ruff"]["required-version"] == "==0.16.0"
    assert data["tool"]["ruff"]["lint"]["select"] == [
        "E4",
        "E7",
        "E9",
        "F",
        "I",
        "UP",
    ]

    assert data["tool"]["ruff"]["lint"]["ignore"] == ["UP042"]


def test_ci_enforces_ruff_lint_and_formatting() -> None:
    text = Path(
        ".github/workflows/tests.yml"
    ).read_text(encoding="utf-8")

    assert (
        f"uv run --locked ruff check {TARGETS}"
        in text
    )
    assert (
        f"uv run --locked ruff format --check {TARGETS}"
        in text
    )


def test_readme_documents_ruff_commands() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## Code quality" in text
    assert f"ruff check {TARGETS}" in text
    assert f"ruff format --check {TARGETS}" in text
