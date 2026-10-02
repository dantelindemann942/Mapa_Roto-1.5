"""Regressions from the Windows 0.1.4 five-ready-clips/failed-job report."""
import asyncio
import io
import json
import os
from pathlib import Path

import app
import desktop


def test_damaged_utf8_marker_cannot_hide_captioned_video(tmp_path):
    stem = "Cambiar de Dimensión [uevP7cbEyPk]"
    filename = f"subtitled_2_hooked_1_{stem}_clip_1.mp4"
    (tmp_path / filename).write_bytes(b"video")
    # Frozen Windows defaults to cp1252 for redirected streams; API is UTF-8.
    broken = filename.encode("cp1252").decode("utf-8", errors="replace")
    app.jobs["windows-regression"] = {"ready_files": {0: broken}}
    try:
        rendered, missing = app._clips_actually_rendered(
            "windows-regression", str(tmp_path), stem, [{}])
        assert missing == 0
        assert rendered[0]["video_url"].endswith(filename)
    finally:
        app.jobs.pop("windows-regression", None)


def test_brackets_in_parent_and_title_are_literal(tmp_path):
    folder = tmp_path / "Proyectos [2026]"
    folder.mkdir()
    stem = "Rick [uevP7cbEyPk]"
    filename = f"subtitled_2_{stem}_clip_1.mp4"
    (folder / filename).write_bytes(b"video")
    assert app._canonical_clip_file(str(folder), stem, 0) == filename


def test_persisted_filename_can_rescue_unusual_output_name(tmp_path):
    (tmp_path / "final_1.mp4").write_bytes(b"video")
    rendered, missing = app._clips_actually_rendered(
        "persisted", str(tmp_path), "old-stem", [{"rendered_file": "final_1.mp4"}])
    assert missing == 0
    assert rendered[0]["video_url"].endswith("final_1.mp4")


def test_manifest_cannot_deliver_file_outside_job(tmp_path):
    (tmp_path / "outside.mp4").write_bytes(b"video")
    folder = tmp_path / "job"
    folder.mkdir()
    rendered, missing = app._clips_actually_rendered(
        "unsafe", str(folder), "absent", [{"rendered_file": "../outside.mp4"}])
    assert rendered == [] and missing == 1


def test_recovery_validates_disk_and_recovers_old_bracket_titles(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    for job_id, has_video in [("valid-recovery", True), ("empty-recovery", False)]:
        folder = tmp_path / job_id
        folder.mkdir()
        stem = "Dimensión [Rick]"
        (folder / f"{stem}_metadata.json").write_text(
            json.dumps({"shorts": [{}]}), encoding="utf-8")
        if has_video:
            (folder / f"subtitled_2_{stem}_clip_1.mp4").write_bytes(b"video")
    try:
        app._recover_jobs_from_disk()
        valid = app.jobs["valid-recovery"]
        assert valid["status"] == "completed"
        assert "subtitled_2_" in valid["result"]["clips"][0]["video_url"]
        assert app.jobs["empty-recovery"]["status"] == "failed"
    finally:
        app.jobs.pop("valid-recovery", None)
        app.jobs.pop("empty-recovery", None)


def test_frozen_streams_explicitly_switch_cp1252_to_utf8(tmp_path, monkeypatch):
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(desktop.sys, "stdout", stdout)
    monkeypatch.setattr(desktop.sys, "stderr", stderr)
    monkeypatch.setattr(desktop, "_data_root", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    # _configure_runtime intentionally sets env; isolate those changes.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    desktop._configure_runtime()
    assert stdout.encoding == stderr.encoding == "utf-8"
    assert stdout.line_buffering and stderr.line_buffering


def test_completed_worker_hands_off_five_clips_not_false_failure(tmp_path, monkeypatch):
    job_id = "five-rendered"
    stem = "Cambiar de Dimensión [uevP7cbEyPk]"
    clips = []
    for i in range(5):
        filename = f"subtitled_2_hooked_1_{stem}_clip_{i+1}.mp4"
        (tmp_path / filename).write_bytes(b"video")
        clips.append({"rendered_file": filename})
    (tmp_path / f"{stem}_metadata.json").write_text(
        json.dumps({"shorts": clips}), encoding="utf-8")
    captured = {}

    class FinishedWorker:
        returncode = 0
        stdout = io.StringIO("✅ Clip 5 ready\n")

        def poll(self):
            return 0

    def popen(*args, **kwargs):
        captured.update(kwargs)
        return FinishedWorker()

    monkeypatch.setattr(app.subprocess, "Popen", popen)
    monkeypatch.setattr(app, "upload_job_artifacts", lambda *a: None)
    app.jobs[job_id] = {"logs": [], "output_dir": str(tmp_path)}
    try:
        asyncio.run(app.run_job(job_id, {"cmd": ["worker"], "env": {},
                                         "output_dir": str(tmp_path)}))
        assert app.jobs[job_id]["status"] == "completed"
        assert len(app.jobs[job_id]["result"]["clips"]) == 5
        assert captured["stdin"] == app.subprocess.DEVNULL
    finally:
        app.jobs.pop(job_id, None)
