from pathlib import Path
import pandas as pd
import pytest
import src.excel_branch_merger.merger as merger


def test_failed_new_output_keeps_previous_successful_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "output"; out.mkdir()
    old_report = out / merger.REPORT_NAME; old_error = out / merger.ERROR_NAME; old_log = out / merger.LOG_NAME
    old_report.write_bytes(b"old-report"); old_error.write_bytes(b"old-error"); old_log.write_text("old-log", encoding="utf-8")
    frame = pd.DataFrame({"customer_name": ["Alice"]})
    summary = pd.DataFrame({"Metric": ["Valid rows"], "Value": [1]})

    original = merger._write_error_workbook
    def fail_error(*args, **kwargs):
        raise OSError("simulated write failure")
    monkeypatch.setattr(merger, "_write_error_workbook", fail_error)
    with pytest.raises(OSError, match="simulated"):
        merger._write_outputs(out, frame, frame, summary, ["new-log"])
    assert old_report.read_bytes() == b"old-report"
    assert old_error.read_bytes() == b"old-error"
    assert old_log.read_text(encoding="utf-8") == "old-log"
    assert not any(path.name.startswith(".excel-branch-merger-") for path in out.iterdir())
    monkeypatch.setattr(merger, "_write_error_workbook", original)
