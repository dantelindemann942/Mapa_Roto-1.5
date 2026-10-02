"""Download every model once so later processing can run fully offline."""
from __future__ import annotations

import gc
import os
import shutil
import subprocess
import time
from pathlib import Path


def _say(message: str) -> None:
    print(message, flush=True)


def _ollama_executable() -> str:
    found = shutil.which("ollama")
    if found:
        return found
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA") or "")
        candidate = local / "Programs" / "Ollama" / "ollama.exe"
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(
        "Ollama no está instalado. Instálalo desde https://ollama.com/download/windows "
        "y déjalo iniciado antes de preparar los modelos.")


def _retry(label: str, action, attempts: int = 3) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            action()
            return
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                _say(f"{label}: intento {attempt}/{attempts} falló; reintentando…")
                time.sleep(min(2 * attempt, 5))
    assert last_error is not None
    raise last_error


def _ensure_free_disk(path: Path, minimum_gb: float = 6.0) -> None:
    path.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(path).free / 1024 ** 3
    if free_gb < minimum_gb:
        raise RuntimeError(
            f"Espacio insuficiente: {free_gb:.1f} GB libres; se requieren "
            f"al menos {minimum_gb:.0f} GB para preparar los modelos.")


def _prepare_ollama(model_name: str) -> None:
    def pull() -> None:
        result = subprocess.run([_ollama_executable(), "pull", model_name])
        if result.returncode != 0:
            raise RuntimeError("ollama pull no pudo completar la descarga")

    _retry("Ollama", pull)


def _prepare_yolo(yolo_target: Path) -> None:
    if yolo_target.is_file() and yolo_target.stat().st_size >= 1_000_000:
        _say(f"YOLO: {yolo_target.name} ya está listo")
        return

    def download() -> None:
        partial = Path("yolov8n.pt")
        if partial.is_file() and partial.stat().st_size < 1_000_000:
            partial.unlink()
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        downloaded = Path(str(getattr(model, "ckpt_path", "yolov8n.pt")))
        if not downloaded.is_file():
            downloaded = Path("yolov8n.pt")
        if not downloaded.is_file() or downloaded.stat().st_size < 1_000_000:
            raise RuntimeError("YOLO no dejó un archivo de pesos utilizable")
        yolo_target.parent.mkdir(parents=True, exist_ok=True)
        if downloaded.resolve() != yolo_target.resolve():
            shutil.copy2(downloaded, yolo_target)
        del model
        gc.collect()

    _retry("YOLO", download)


def _prepare_whisper(whisper_name: str) -> None:
    def download() -> None:
        from faster_whisper import WhisperModel
        whisper = WhisperModel(whisper_name, device="cpu", compute_type="int8")
        del whisper
        gc.collect()

    _retry("Faster-Whisper", download)


def prepare() -> int:
    model_name = os.environ.get("VISION_MODEL") or "qwen3.5:4b"
    models_dir = Path(os.environ.get("MAPA_ROTO_DATA_DIR") or "local-data") / "models"
    yolo_target = Path(os.environ.get("YOLO_MODEL_PATH") or models_dir / "yolov8n.pt")
    whisper_name = os.environ.get("WHISPER_MODEL") or "small"

    _ensure_free_disk(models_dir)
    failures: list[str] = []
    stages = [
        (f"[1/3] Ollama: descargando/verificando {model_name}",
         lambda: _prepare_ollama(model_name)),
        (f"[2/3] YOLO: preparando {yolo_target.name}",
         lambda: _prepare_yolo(yolo_target)),
        (f"[3/3] Faster-Whisper: preparando {whisper_name} CPU int8",
         lambda: _prepare_whisper(whisper_name)),
    ]
    for message, action in stages:
        _say(message)
        try:
            action()
        except Exception as exc:
            stage = message.split(":", 1)[0].split("]", 1)[-1].strip()
            failures.append(f"{stage}: {exc}")
            _say(f"ERROR {stage}: {exc}")

    if failures:
        raise RuntimeError(
            "No se pudieron preparar todos los modelos. Puedes reintentar sin "
            "perder las descargas completadas. " + " | ".join(failures))
    _say("LISTO: Qwen, YOLO y Faster-Whisper están disponibles sin Internet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(prepare())
