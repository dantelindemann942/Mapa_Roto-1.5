"""Windows desktop launcher for MAPA ROTO Clip.

The packaged executable has two modes:
  * normal: FastAPI on loopback + native WebView2 window
  * --worker: run the OpenShorts pipeline for one queued source
"""
from __future__ import annotations

import os
import runpy
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path


_DESKTOP_LOG_STREAM = None


def _ensure_standard_streams(data_root: Path) -> Path | None:
    """Give GUI builds valid stdout/stderr streams.

    PyInstaller sets both streams to ``None`` for ``console=False`` builds.
    Uvicorn's colour formatter calls ``sys.stderr.isatty()`` during startup,
    so the desktop executable must install a real stream before importing it.
    Keeping the stream in a module global also prevents it from being garbage
    collected while the native window is open.
    """
    global _DESKTOP_LOG_STREAM

    if sys.stdout is not None and sys.stderr is not None:
        return None

    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "desktop.log"
    try:
        stream = open(log_path, "a", encoding="utf-8", buffering=1)
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")

    _DESKTOP_LOG_STREAM = stream
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    return log_path


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _data_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "MAPA ROTO Clip"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "mapa-roto-clip"


def _configure_runtime() -> Path:
    bundle = _bundle_root()
    data = _data_root()
    data.mkdir(parents=True, exist_ok=True)
    _ensure_standard_streams(data)
    # Frozen Python ignores PYTHONIOENCODING. A pipe on Spanish Windows may
    # otherwise use cp1252, while the API reads UTF-8, corrupting CLIP_READY.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    os.chdir(data)

    ffmpeg_bin = bundle / "vendor" / "ffmpeg" / "bin"
    path_entries = [str(ffmpeg_bin), str(bundle)]
    os.environ["PATH"] = os.pathsep.join(path_entries + [os.environ.get("PATH", "")])
    os.environ.setdefault("MAPA_ROTO_DATA_DIR", str(data / "state"))
    os.environ.setdefault("YOLO_MODEL_PATH", str(data / "state" / "models" / "yolov8n.pt"))
    os.environ.setdefault("MAPA_ROTO_DESKTOP_WORKER", "1")
    worker_exe = Path(sys.executable).with_name("MapaRotoWorker.exe")
    if worker_exe.is_file():
        os.environ.setdefault("MAPA_ROTO_WORKER_EXE", str(worker_exe))
    os.environ.setdefault("BILLING_ENABLED", "0")
    os.environ.setdefault("DISABLE_YOUTUBE_URL", "true")
    os.environ.setdefault("MAX_CONCURRENT_JOBS", "1")
    os.environ.setdefault("CLIP_WORKERS", "1")
    os.environ.setdefault("TRANSCRIBE_BACKEND", "whisper")
    os.environ.setdefault("WHISPER_MODEL", "small")
    os.environ.setdefault("WHISPER_DEVICE", "cpu")
    os.environ.setdefault("WHISPER_COMPUTE", "int8")
    os.environ.setdefault("WHISPER_LANGUAGE", "es")
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    os.environ.setdefault("LLM_MODEL", "qwen3.5:4b")
    os.environ.setdefault("VISION_PROVIDER", "ollama")
    os.environ.setdefault("VISION_MODEL", "qwen3.5:4b")
    os.environ.setdefault("AUTO_LAYOUT", "1")
    os.environ.setdefault("FFMPEG_ENCODER", "qsv")
    os.environ.setdefault("AUTO_CAPTIONS", "1")
    os.environ.setdefault("JOB_RETENTION_SECONDS", str(365 * 24 * 60 * 60))
    os.environ.setdefault("OUTPUT_MAX_GB", "80")
    os.environ.setdefault("UPLOADS_MAX_GB", "40")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    return bundle


def _worker_mode() -> bool:
    if "--worker" not in sys.argv:
        return False
    index = sys.argv.index("--worker")
    sys.argv = [sys.argv[0], *sys.argv[index + 1:]]
    runpy.run_module("main", run_name="__main__")
    return True


def _setup_mode() -> bool:
    if "--setup-models" not in sys.argv:
        return False
    from model_setup import prepare
    raise SystemExit(prepare())


def _self_test_mode() -> bool:
    if "--self-test" not in sys.argv:
        return False
    from local_app import app
    paths = {getattr(route, "path", "") for route in app.routes}
    required = {"/api/process", "/api/local/system", "/api/local/profiles"}
    missing = required - paths
    if missing:
        raise RuntimeError(f"Missing packaged routes: {sorted(missing)}")
    ui = _bundle_root() / "local-ui" / "dist" / "index.html"
    if not ui.is_file():
        raise RuntimeError("Packaged UI is missing")

    from packaged_smoke import run_smoke
    run_smoke()

    # Import the complete offline inference stack from the packaged executable.
    # This intentionally catches modules that PyInstaller may omit even though
    # the source environment can import them (for example torch.distributed,
    # which Ultralytics reaches through torch.utils.data).
    import torch.distributed  # noqa: F401
    from torch.utils.data import DataLoader  # noqa: F401
    from ultralytics import YOLO  # noqa: F401
    import lap  # noqa: F401
    from faster_whisper import WhisperModel  # noqa: F401
    import mediapipe  # noqa: F401
    import ctranslate2

    cpu_compute_types = ctranslate2.get_supported_compute_types("cpu")
    if "int8" not in cpu_compute_types:
        raise RuntimeError(
            f"CTranslate2 CPU int8 unavailable: {sorted(cpu_compute_types)}")
    print("MAPA ROTO Clip self-test OK", flush=True)
    return True


def _detached_self_test_mode() -> bool:
    if "--self-test-detached" not in sys.argv:
        return False
    from packaged_smoke import UTF8_SENTINEL
    worker = os.environ.get("MAPA_ROTO_WORKER_EXE")
    if not worker:
        raise RuntimeError("Packaged worker executable is missing")
    result = subprocess.run(
        [worker, "--self-test"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="strict", timeout=300,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    print(result.stdout, flush=True)
    if result.returncode or UTF8_SENTINEL not in result.stdout:
        raise RuntimeError(f"Detached UTF-8 worker self-test failed ({result.returncode})")
    return True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_crash_report(exc: BaseException) -> Path | None:
    """Persist a traceback even when the frozen worker loses its pipe."""
    explicit = (os.environ.get("MAPA_ROTO_JOB_LOG") or "").strip()
    path = (Path(explicit) if explicit
            else _data_root() / "logs" / "desktop-crash.log")
    report = (
        f"\n[{datetime.now().astimezone().isoformat(timespec='seconds')}] "
        f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}\n"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(report)
            handle.flush()
        return path
    except OSError:
        return None


def main() -> int:
    _configure_runtime()
    if _detached_self_test_mode():
        return 0
    if _self_test_mode():
        return 0
    if _setup_mode():
        return 0
    if _worker_mode():
        return 0

    import uvicorn
    from local_app import app

    port = _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        use_colors=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="mapa-roto-api", daemon=True)
    thread.start()

    deadline = time.time() + 15
    while not server.started and thread.is_alive() and time.time() < deadline:
        time.sleep(0.05)
    if not thread.is_alive() or not server.started:
        server.should_exit = True
        raise RuntimeError("El servidor local no pudo iniciar")

    url = f"http://127.0.0.1:{port}"
    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        try:
            while thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            server.should_exit = True
        return 0

    window = webview.create_window(
        "MAPA ROTO Clip · Local",
        url,
        width=1440,
        height=920,
        min_size=(1080, 700),
        background_color="#080808",
    )
    try:
        webview.start(debug=False, private_mode=False)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        report = _write_crash_report(exc)
        print(f"FATAL_WORKER_ERROR {type(exc).__name__}: {exc}", flush=True)
        if report:
            print(f"FATAL_WORKER_LOG {report}", flush=True)
        traceback.print_exc()
        raise
