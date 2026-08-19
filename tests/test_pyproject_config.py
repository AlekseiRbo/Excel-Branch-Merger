import tomllib
from pathlib import Path


def load_pyproject() -> dict:
    path = Path("pyproject.toml")
    assert path.is_file(), "pyproject.toml must exist"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_pyproject_contains_canonical_project_metadata() -> None:
    data = load_pyproject()
    project = data["project"]

    assert project["name"] == "excel-branch-merger"
    assert project["version"] == "1.3"
    assert project["requires-python"] == ">=3.11"
    assert project["license"] == "MIT"


def test_pyproject_declares_runtime_dependencies() -> None:
    data = load_pyproject()
    dependencies = set(data["project"]["dependencies"])

    assert "pandas>=2.2,<3.0" in dependencies
    assert "openpyxl>=3.1,<4.0" in dependencies
    assert "Pillow>=10.0,<13.0" in dependencies


def test_pyproject_declares_pytest_as_development_dependency() -> None:
    data = load_pyproject()

    assert "pytest>=8.0,<9.0" in data["dependency-groups"]["dev"]


def test_pytest_configuration_moved_to_pyproject() -> None:
    data = load_pyproject()
    pytest_config = data["tool"]["pytest"]["ini_options"]

    assert pytest_config["pythonpath"] == ["."]
    assert pytest_config["testpaths"] == ["tests"]
    assert pytest_config["addopts"] == "-ra"

    assert not Path("pytest.ini").exists()


def test_readme_reflects_pyproject_migration() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "pyproject.toml" in text
    assert "pytest.ini" not in text
