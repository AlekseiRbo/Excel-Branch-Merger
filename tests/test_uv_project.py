from pathlib import Path


def test_uv_lock_replaces_legacy_requirements() -> None:
    assert Path("uv.lock").is_file()
    assert not Path("requirements.txt").exists()


def test_readme_uses_locked_uv_installation() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "uv sync --locked" in text
    assert "python -m pip install -r requirements.txt" not in text
    assert "uv.lock" in text


def test_github_actions_uses_uv() -> None:
    workflow = Path(".github/workflows/tests.yml")
    assert workflow.is_file()

    text = workflow.read_text(encoding="utf-8")

    assert "astral-sh/setup-uv@" in text
    assert 'version: "0.12.3"' in text
    assert "uv lock --check" in text
    assert "uv sync --locked" in text
    assert "uv run --locked python -m pytest -q" in text
    assert "uv run --locked python -m compileall -q src gui.py main.py" in text

    assert "pip install -r requirements.txt" not in text
