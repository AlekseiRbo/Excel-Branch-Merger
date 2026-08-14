from pathlib import Path


def test_github_actions_runs_tests_and_compile_check() -> None:
    workflow = Path(".github/workflows/tests.yml")
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    assert "pull_request:" in text
    assert "push:" in text
    assert "python -m pytest -q" in text
    assert "python -m compileall -q src gui.py main.py" in text
