from pathlib import Path

import gui


def test_default_config_prefers_processing_yaml(tmp_path: Path) -> None:
    legacy = tmp_path / "config.json"
    processing = tmp_path / "processing.yaml"

    legacy.write_text("{}", encoding="utf-8")
    processing.write_text("fields: {}", encoding="utf-8")

    assert gui.default_config_path(tmp_path) == processing


def test_default_config_falls_back_to_legacy_json(tmp_path: Path) -> None:
    legacy = tmp_path / "config.json"
    legacy.write_text("{}", encoding="utf-8")

    assert gui.default_config_path(tmp_path) == legacy


def test_default_config_uses_processing_yaml_when_no_file_exists(
    tmp_path: Path,
) -> None:
    assert gui.default_config_path(tmp_path) == (tmp_path / "processing.yaml")


def test_gui_source_exposes_configuration_file_chooser() -> None:
    source = Path("gui.py").read_text(encoding="utf-8")

    assert 'text="Configuration file"' in source
    assert '"browse-config"' in source
    assert "askopenfilename" in source
    assert "*.yaml" in source
    assert "*.yml" in source
    assert "*.json" in source


def test_processing_worker_receives_selected_config_path() -> None:
    source = Path("gui.py").read_text(encoding="utf-8")

    assert "self.config_var" in source
    assert "config_path = Path(self.config_var.get())" in source
    assert "args=(input_dir, output_dir, config_path)" in source
    assert "def _run_processing(" in source
    assert "config_path: Path" in source
    assert "load_config(config_path)" in source


def test_start_processing_rejects_missing_configuration_file() -> None:
    source = Path("gui.py").read_text(encoding="utf-8")

    assert "if not config_path.is_file():" in source
    assert "Please select a valid configuration file." in source
