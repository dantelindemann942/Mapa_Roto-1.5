"""Local-only API and desktop surface layered over the OpenShorts pipeline."""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import Body, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

import app as upstream
import ffmpeg_utils
import local_job_logs
import local_profiles
import local_vision
from mapa_roto_version import __version__


app = upstream.app
os.environ.setdefault(
    "YOLO_MODEL_PATH", str(local_profiles.data_dir() / "models" / "yolov8n.pt"))
_SETUP_JOBS: dict[str, dict[str, Any]] = {}
_SETUP_LOCK = threading.Lock()


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _command_version(command: list[str], timeout: float = 4.0) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                stdin=subprocess.DEVNULL,
                                encoding="utf-8", errors="replace", timeout=timeout)
        line = (result.stdout or result.stderr or "").splitlines()
        return {"ok": result.returncode == 0, "detail": line[0][:180] if line else "OK"}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)[:180]}


def _ollama_status() -> dict:
    url = f"{local_vision.base_url()}/api/tags"
    try:
        response = httpx.get(url, timeout=2.5)
        response.raise_for_status()
        models = [str(item.get("name") or item.get("model") or "")
                  for item in (response.json().get("models") or [])]
        wanted = local_vision.model_name()
        installed = any(
            name == wanted
            or (":" not in wanted and name.split(":", 1)[0] == wanted)
            for name in models
        )
        return {"ok": True, "detail": "Ollama activo", "models": models,
                "model": wanted, "modelInstalled": installed}
    except Exception as exc:
        return {"ok": False,
                "detail": "Ollama no responde; instálalo o abre su servicio local",
                "error": str(exc)[:180], "models": [],
                "model": local_vision.model_name(), "modelInstalled": False}


def _whisper_model_cached() -> bool:
    model = (os.environ.get("WHISPER_MODEL") or "small").replace("/", "--")
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        candidates = [
            Path(HF_HUB_CACHE) / f"models--Systran--faster-whisper-{model}",
            Path(HF_HUB_CACHE) / f"models--mobiuslabsgmbh--faster-whisper-{model}",
        ]
        return any((path / "snapshots").is_dir()
                   and any((path / "snapshots").iterdir()) for path in candidates)
    except Exception:
        return False


@app.get("/api/local/about")
async def local_about():
    return {
        "name": "MAPA ROTO Clip",
        "version": __version__,
        "mode": "offline-local",
        "upstream": "OpenShorts",
        "networkPolicy": "loopback-only AI inference",
    }


@app.get("/api/local/system")
async def local_system():
    ffmpeg = _command_version(["ffmpeg", "-version"])
    ffprobe = _command_version(["ffprobe", "-version"])
    ollama = _ollama_status()
    try:
        qsv = bool(ffmpeg_utils.qsv_available()) if ffmpeg["ok"] else False
        qsv_detail = "Intel Quick Sync disponible" if qsv else "No respondió; se usará CPU"
    except Exception as exc:
        qsv, qsv_detail = False, str(exc)[:180]
    disk = shutil.disk_usage(Path.cwd())
    whisper_package = importlib.util.find_spec("faster_whisper") is not None
    whisper_cached = _whisper_model_cached() if whisper_package else False
    yolo_package = importlib.util.find_spec("ultralytics") is not None
    yolo_path = Path(os.environ["YOLO_MODEL_PATH"])
    components = {
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
        "quickSync": {"ok": qsv, "detail": qsv_detail},
        "ollama": ollama,
        "fasterWhisper": {
            "ok": whisper_package and whisper_cached,
            "detail": (os.environ.get("WHISPER_MODEL", "small") + " · CPU int8 · español"
                       + (" · modelo listo" if whisper_cached else " · falta descargar modelo")),
        },
        "yolo": {
            "ok": yolo_package and yolo_path.is_file(),
            "detail": "Ultralytics YOLO local" + (" · pesos listos" if yolo_path.is_file()
                                                    else " · faltan pesos"),
        },
        "mediaPipe": {
            "ok": importlib.util.find_spec("mediapipe") is not None,
            "detail": "Seguimiento facial local",
        },
    }
    return {
        "ready": all(components[key]["ok"] for key in
                     ("ffmpeg", "ffprobe", "ollama", "fasterWhisper", "yolo", "mediaPipe"))
                 and ollama["modelInstalled"],
        "components": components,
        "memoryProfile": "16 GB · 1 trabajo simultáneo",
        "freeDiskGb": round(disk.free / 1024 ** 3, 1),
        "dataDir": str(Path.cwd()),
    }


@app.get("/api/local/profiles")
async def local_profile_list():
    return {"profiles": local_profiles.list_profiles()}


@app.post("/api/local/profiles")
async def local_profile_create(payload: dict = Body(...)):
    try:
        return local_profiles.create_profile(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/api/local/profiles/{profile_id}")
async def local_profile_update(profile_id: str, payload: dict = Body(...)):
    try:
        return local_profiles.update_profile(profile_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Profile not found")
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/local/profiles/{profile_id}")
async def local_profile_delete(profile_id: str):
    try:
        local_profiles.delete_profile(profile_id)
        return {"deleted": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Profile not found")
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def _history_item(job_id: str, job_dir: Path) -> dict | None:
    metadata_files = list(job_dir.glob("*_metadata.json"))
    memory = upstream.jobs.get(job_id) or {}
    if not metadata_files:
        if memory:
            return {
                "id": job_id,
                "status": memory.get("status", "queued"),
                "createdAt": int(job_dir.stat().st_mtime * 1000),
                "title": "Procesando…",
                "clips": (memory.get("result") or {}).get("clips") or [],
            }
        return None
    metadata_path = metadata_files[0]
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    clips = data.get("shorts") or []
    base_name = metadata_path.name[:-len("_metadata.json")]
    rendered, _ = upstream._clips_actually_rendered(job_id, str(job_dir), base_name, clips)
    source_name = str(data.get("source_video") or base_name)
    return {
        "id": job_id,
        "status": memory.get("status", "completed"),
        "createdAt": int(job_dir.stat().st_mtime * 1000),
        "title": Path(source_name).stem,
        "format": data.get("output_format", "vertical"),
        "clips": rendered,
        "clipCount": len(rendered),
    }


@app.get("/api/local/history")
async def local_history():
    root = Path(upstream.OUTPUT_DIR)
    root.mkdir(parents=True, exist_ok=True)
    items = []
    for job_dir in root.iterdir():
        if not job_dir.is_dir() or job_dir.name == "thumbnails":
            continue
        item = _history_item(job_dir.name, job_dir)
        if item:
            items.append(item)
    items.sort(key=lambda item: item.get("createdAt", 0), reverse=True)
    return {"projects": items}


@app.post("/api/local/open-output")
async def local_open_output():
    output = Path(upstream.OUTPUT_DIR).resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            os.startfile(str(output))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(output)])
        else:
            subprocess.Popen(["xdg-open", str(output)])
        return {"opened": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/local/diagnostics/{job_id}")
async def local_job_diagnostics(job_id: str):
    """Download one shareable report for a failed/finished local job."""
    if not re.fullmatch(r"[A-Za-z0-9-]{6,64}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job id")
    output_root = Path(upstream.OUTPUT_DIR).resolve()
    job_dir = (output_root / job_id).resolve()
    if job_dir.parent != output_root or not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="Job diagnostics not found")
    memory = upstream.jobs.get(job_id) or {}
    failure = local_job_logs.read_failure(job_dir)
    status = str(memory.get("status") or ("failed" if failure else "unknown"))
    report = local_job_logs.diagnostic_report(
        job_id,
        job_dir,
        __version__,
        status=status,
        desktop_log=Path.cwd() / "logs" / "desktop.log",
    )
    handle = tempfile.NamedTemporaryFile(
        prefix=f"MAPA-ROTO-diagnostico-{job_id[:8]}-",
        suffix=".txt",
        delete=False,
        mode="w",
        encoding="utf-8",
    )
    try:
        handle.write(report)
        handle.close()
    except Exception:
        handle.close()
        try:
            os.remove(handle.name)
        except OSError:
            pass
        raise
    return FileResponse(
        handle.name,
        media_type="text/plain; charset=utf-8",
        filename=f"MAPA-ROTO-diagnostico-{job_id[:8]}.txt",
        background=BackgroundTask(
            lambda: os.path.exists(handle.name) and os.remove(handle.name)),
    )


@app.get("/api/local/batch-export")
async def local_batch_export(jobs: str):
    """One ZIP containing the delivered clips from several queued sources."""
    job_ids = [item.strip() for item in jobs.split(",") if item.strip()]
    if not job_ids or len(job_ids) > 25:
        raise HTTPException(status_code=400, detail="Select between 1 and 25 jobs")
    if any(not re.fullmatch(r"[A-Za-z0-9-]{6,64}", item) for item in job_ids):
        raise HTTPException(status_code=400, detail="Invalid job id")
    handle = tempfile.NamedTemporaryFile(prefix="mapa_roto_lote_", suffix=".zip", delete=False)
    zip_path = handle.name
    handle.close()
    written = 0
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for job_id in job_ids:
                job_dir = Path(upstream.OUTPUT_DIR) / job_id
                if not job_dir.is_dir():
                    continue
                item = _history_item(job_id, job_dir)
                if not item:
                    continue
                folder = (re.sub(r"[^A-Za-z0-9._ -]+", "_",
                                 item.get("title") or job_id).strip(" ._")[:80]
                          or job_id)
                for index, clip in enumerate(item.get("clips") or [], 1):
                    filename = Path(str(clip.get("video_url") or "")).name
                    path = job_dir / filename
                    if path.is_file() and path.stat().st_size > 0:
                        archive.write(path, f"{folder}/{index:02d}_{filename}")
                        written += 1
        if not written:
            os.remove(zip_path)
            raise HTTPException(status_code=404, detail="No finished clips found")
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"MAPA_ROTO_lote_{int(time.time())}.zip",
            background=BackgroundTask(lambda: os.path.exists(zip_path) and os.remove(zip_path)),
        )
    except HTTPException:
        raise
    except Exception as exc:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(status_code=500, detail=str(exc))


def _run_model_pull(setup_id: str) -> None:
    job = _SETUP_JOBS[setup_id]
    worker = (os.environ.get("MAPA_ROTO_WORKER_EXE") or "").strip()
    if worker:
        command = [worker, "--setup-models"]
    elif os.environ.get("MAPA_ROTO_DESKTOP_WORKER") == "1":
        command = [sys.executable, "--setup-models"]
    else:
        command = [sys.executable, str(Path(__file__).with_name("model_setup.py"))]
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                stdin=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace",
                                creationflags=(subprocess.CREATE_NO_WINDOW
                                               if os.name == "nt" and worker else 0))
        job["status"] = "running"
        for line in iter(proc.stdout.readline, ""):
            clean = line.strip()
            if clean:
                with _SETUP_LOCK:
                    job["logs"] = (job["logs"] + [clean])[-80:]
        code = proc.wait()
        job["status"] = "completed" if code == 0 else "failed"
        job["exitCode"] = code
    except Exception as exc:
        job["status"] = "failed"
        job["logs"].append(str(exc))


@app.post("/api/local/setup/qwen")
@app.post("/api/local/setup/all")
async def local_setup_qwen():
    setup_id = uuid.uuid4().hex
    _SETUP_JOBS[setup_id] = {"id": setup_id, "status": "queued", "logs": [],
                              "model": local_vision.model_name()}
    thread = threading.Thread(target=_run_model_pull, args=(setup_id,), daemon=True)
    thread.start()
    return _SETUP_JOBS[setup_id]


@app.get("/api/local/setup/{setup_id}")
async def local_setup_status(setup_id: str):
    job = _SETUP_JOBS.get(setup_id)
    if not job:
        raise HTTPException(status_code=404, detail="Setup job not found")
    return job


# The Vite build is mounted last so API/video routes keep precedence. In source
# development it may not exist yet; `npm run dev` then serves the UI separately.
_UI_DIR = _bundle_root() / "local-ui" / "dist"
if _UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_UI_DIR), html=True), name="mapa-roto-ui")
