from pathlib import Path

import desktop


def test_gui_build_creates_valid_standard_streams(monkeypatch, tmp_path: Path):
    original_stdout = desktop.sys.stdout
    original_stderr = desktop.sys.stderr
    monkeypatch.setattr(desktop.sys, "stdout", None)
    monkeypatch.setattr(desktop.sys, "stderr", None)

    try:
        log_path = desktop._ensure_standard_streams(tmp_path)

        assert log_path == tmp_path / "logs" / "desktop.log"
        assert desktop.sys.stdout is desktop.sys.stderr
        assert desktop.sys.stderr.isatty() is False
        desktop.sys.stderr.write("desktop startup test\n")
        desktop.sys.stderr.flush()
        assert "desktop startup test" in log_path.read_text(encoding="utf-8")
    finally:
        stream = desktop._DESKTOP_LOG_STREAM
        monkeypatch.setattr(desktop.sys, "stdout", original_stdout)
        monkeypatch.setattr(desktop.sys, "stderr", original_stderr)
        if stream is not None and not stream.closed:
            stream.close()
        desktop._DESKTOP_LOG_STREAM = None


def test_worker_crash_report_uses_job_specific_path(monkeypatch, tmp_path: Path):
    target = tmp_path / "output" / "job-1" / "worker-crash.log"
    monkeypatch.setenv("MAPA_ROTO_JOB_LOG", str(target))

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        written = desktop._write_crash_report(exc)

    assert written == target
    text = target.read_text(encoding="utf-8")
    assert "RuntimeError: boom" in text
    assert "Traceback" in text
