from pathlib import Path

import pytest

import model_setup


def test_prepare_continues_after_one_stage_fails(monkeypatch, tmp_path: Path):
    completed = []
    monkeypatch.setenv("MAPA_ROTO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(model_setup, "_ensure_free_disk", lambda path: None)
    monkeypatch.setattr(
        model_setup, "_prepare_ollama", lambda model: completed.append("ollama"))

    def fail_yolo(path):
        raise ModuleNotFoundError("No module named 'torch.distributed'")

    monkeypatch.setattr(model_setup, "_prepare_yolo", fail_yolo)
    monkeypatch.setattr(
        model_setup, "_prepare_whisper", lambda model: completed.append("whisper"))

    with pytest.raises(RuntimeError, match="torch.distributed"):
        model_setup.prepare()

    assert completed == ["ollama", "whisper"]


def test_prepare_succeeds_when_all_stages_complete(monkeypatch, tmp_path: Path):
    completed = []
    monkeypatch.setenv("MAPA_ROTO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(model_setup, "_ensure_free_disk", lambda path: None)
    monkeypatch.setattr(
        model_setup, "_prepare_ollama", lambda model: completed.append("ollama"))
    monkeypatch.setattr(
        model_setup, "_prepare_yolo", lambda path: completed.append("yolo"))
    monkeypatch.setattr(
        model_setup, "_prepare_whisper", lambda model: completed.append("whisper"))

    assert model_setup.prepare() == 0
    assert completed == ["ollama", "yolo", "whisper"]
