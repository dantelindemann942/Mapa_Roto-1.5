import json

import local_job_logs


def test_pipeline_and_failure_logs_are_durable(tmp_path):
    local_job_logs.append(tmp_path, "Transcribiendo 25%")
    local_job_logs.append(tmp_path, "RuntimeError: respuesta vacía")
    path = local_job_logs.write_failure(
        tmp_path, 1, "RuntimeError: respuesta vacía",
        ["Transcribiendo 25%", "RuntimeError: respuesta vacía"])

    assert "Transcribiendo 25%" in (
        tmp_path / local_job_logs.PIPELINE_LOG).read_text(encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["returncode"] == 1
    assert payload["summary"] == "RuntimeError: respuesta vacía"


def test_diagnostic_report_contains_all_available_logs(tmp_path):
    local_job_logs.append(tmp_path, "línea pipeline")
    (tmp_path / local_job_logs.WORKER_CRASH_LOG).write_text(
        "Traceback\nRuntimeError: boom\n", encoding="utf-8")
    desktop = tmp_path / "desktop.log"
    desktop.write_text("desktop tail\n", encoding="utf-8")
    local_job_logs.write_failure(tmp_path, 1, "boom", ["boom"])

    report = local_job_logs.diagnostic_report(
        "job-123456", tmp_path, "0.1.4", "failed", desktop)

    assert "Versión: 0.1.4" in report
    assert "línea pipeline" in report
    assert "RuntimeError: boom" in report
    assert "desktop tail" in report


def test_diagnostic_lists_rendered_files_and_sizes(tmp_path):
    (tmp_path / "Rick_dimensión_[123]_clip_1.mp4").write_bytes(b"video")
    report = local_job_logs.diagnostic_report("inventory", tmp_path, "0.1.5")
    assert "ARCHIVOS DE SALIDA" in report
    assert "Rick_dimensión_[123]_clip_1.mp4 | 5 bytes" in report
