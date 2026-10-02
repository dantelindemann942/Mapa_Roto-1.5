"""Durable, local-only diagnostics for desktop worker jobs."""
from __future__ import annotations

import json
import os
import platform
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PIPELINE_LOG = "pipeline.log"
FAILURE_JSON = "failure.json"
WORKER_CRASH_LOG = "worker-crash.log"
_LOCK = threading.Lock()


def _stamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def append(output_dir: str | os.PathLike, line: object) -> Path:
    """Append one flushed UTF-8 line and return the log path."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / PIPELINE_LOG
    clean = str(line or "").replace("\x00", "").rstrip("\r\n")
    if len(clean) > 20_000:
        clean = clean[:20_000] + " …[truncated]"
    with _LOCK:
        with path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(f"[{_stamp()}] {clean}\n")
            handle.flush()
    return path


def write_failure(output_dir: str | os.PathLike, returncode: int | None,
                  summary: str, logs: Iterable[object]) -> Path:
    """Atomically persist the failure summary plus a compact log tail."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / FAILURE_JSON
    payload = {
        "created_at": _stamp(),
        "returncode": returncode,
        "summary": str(summary or "El worker terminó sin explicar la causa."),
        "log_tail": [str(line) for line in list(logs)[-80:]],
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    os.replace(temp, path)
    return path


def tail(path: str | os.PathLike, max_lines: int = 250) -> list[str]:
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as handle:
            lines = list(deque(handle, maxlen=max(1, int(max_lines))))
    except OSError:
        return []
    return [line.rstrip("\r\n") for line in lines]


def read_failure(output_dir: str | os.PathLike) -> dict:
    try:
        value = json.loads((Path(output_dir) / FAILURE_JSON).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def diagnostic_report(job_id: str, output_dir: str | os.PathLike,
                      version: str, status: str = "unknown",
                      desktop_log: str | os.PathLike | None = None) -> str:
    """Build a shareable text report without source video bytes or secrets."""
    root = Path(output_dir)
    failure = read_failure(root)
    sections = [
        "MAPA ROTO Clip - diagnóstico local",
        f"Versión: {version}",
        f"Trabajo: {job_id}",
        f"Estado: {status}",
        f"Generado: {_stamp()}",
        f"Windows/OS: {platform.platform()}",
        f"Python empaquetado: {sys.version.split()[0]}",
        f"Código de salida: {failure.get('returncode', 'no registrado')}",
        f"Resumen: {failure.get('summary', 'no registrado')}",
        "",
    ]
    sections.extend(["=== ARCHIVOS DE SALIDA (hasta 100) ==="])
    try:
        files = sorted(root.iterdir(), key=lambda path: path.name)[:100]
        for path in files:
            if path.is_file():
                try:
                    sections.append(f"{path.name} | {path.stat().st_size} bytes")
                except OSError as exc:
                    sections.append(f"{path.name} | error al consultar archivo: {exc}")
    except OSError as exc:
        sections.append(f"No se pudo revisar la carpeta: {exc}")
    sections.extend(["", "=== PIPELINE.LOG ==="])
    pipeline = tail(root / PIPELINE_LOG, 500)
    sections.extend(pipeline or ["(sin pipeline.log)"])
    sections.extend(["", "=== WORKER-CRASH.LOG ==="])
    crash = tail(root / WORKER_CRASH_LOG, 250)
    sections.extend(crash or ["(sin worker-crash.log)"])
    if desktop_log:
        sections.extend(["", "=== DESKTOP.LOG (últimas líneas) ==="])
        desktop = tail(desktop_log, 250)
        sections.extend(desktop or ["(sin desktop.log)"])
    sections.extend(["", "Fin del diagnóstico."])
    return "\n".join(sections) + "\n"
