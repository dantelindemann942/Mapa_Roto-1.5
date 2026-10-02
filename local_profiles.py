"""Persistent MAPA ROTO editing profiles for the local desktop application."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path


_LOCK = threading.Lock()


def data_dir() -> Path:
    root = os.environ.get("MAPA_ROTO_DATA_DIR") or "local-data"
    path = Path(root).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def profiles_path() -> Path:
    return data_dir() / "profiles.json"


def _caption(highlight: str, size: int = 44, position: str = "bottom",
             max_chars: int = 16) -> dict:
    return {
        "style": "karaoke",
        "alignment": position,
        "font_name": "Anton",
        "font_size": size,
        "font_color": "#FFFFFF",
        "highlight_color": highlight,
        "border_color": "#050505",
        "border_width": 5,
        "effect": "pop",
        "base_opacity": 1.0,
        "uppercase": True,
        "max_chars": max_chars,
        "max_duration": 1.35,
    }


BUILTIN_PROFILES = [
    {
        "id": "mapa-roto",
        "name": "MAPA ROTO",
        "description": "Impacto alto, rojo de marca y encuadre automático.",
        "accent": "#ff2d2d",
        "builtin": True,
        "target_clips": 5,
        "min_seconds": 20,
        "max_seconds": 55,
        "output_format": "vertical",
        "layouts": ["split", "screencast", "punch_in"],
        "captions": True,
        "caption_style": _caption("#FF2D2D"),
        "auto_hook": True,
        "auto_hook_style": "red",
        "encoder": "qsv",
        "whisper_model": "small",
        "whisper_language": "es",
    },
    {
        "id": "gaming",
        "name": "GAMEPLAY",
        "description": "Momentos visuales, jugadas y ritmo corto.",
        "accent": "#7c5cff",
        "builtin": True,
        "target_clips": 6,
        "min_seconds": 15,
        "max_seconds": 38,
        "output_format": "vertical",
        "layouts": ["punch_in"],
        "captions": True,
        "caption_style": _caption("#8CFF4D", size=42),
        "auto_hook": True,
        "auto_hook_style": "outline_yellow",
        "encoder": "qsv",
        "whisper_model": "small",
        "whisper_language": "es",
    },
    {
        "id": "podcast",
        "name": "PODCAST",
        "description": "Diálogo, dos personas y subtítulo legible.",
        "accent": "#ffb020",
        "builtin": True,
        "target_clips": 5,
        "min_seconds": 30,
        "max_seconds": 75,
        "output_format": "vertical",
        "layouts": ["split", "speaker_cut"],
        "captions": True,
        "caption_style": _caption("#FFE500", size=42, max_chars=18),
        "auto_hook": True,
        "auto_hook_style": "classic",
        "encoder": "qsv",
        "whisper_model": "small",
        "whisper_language": "es",
    },
    {
        "id": "tutorial",
        "name": "TUTORIAL / PANTALLA",
        "description": "Preserva software, slides, tablas y texto en pantalla.",
        "accent": "#32d5ff",
        "builtin": True,
        "target_clips": 4,
        "min_seconds": 25,
        "max_seconds": 60,
        "output_format": "vertical",
        "layouts": ["screencast", "punch_in"],
        "captions": True,
        "caption_style": _caption("#32D5FF", size=40, position="middle", max_chars=18),
        "auto_hook": True,
        "auto_hook_style": "outline",
        "encoder": "qsv",
        "whisper_model": "small",
        "whisper_language": "es",
    },
]


def _read() -> list[dict]:
    path = profiles_path()
    if not path.exists():
        _write(BUILTIN_PROFILES)
        return json.loads(json.dumps(BUILTIN_PROFILES))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
    except (OSError, ValueError):
        pass
    _write(BUILTIN_PROFILES)
    return json.loads(json.dumps(BUILTIN_PROFILES))


def _write(profiles: list[dict]) -> None:
    path = profiles_path()
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def list_profiles() -> list[dict]:
    with _LOCK:
        return _read()


def get_profile(profile_id: str) -> dict | None:
    return next((p for p in list_profiles() if p.get("id") == profile_id), None)


def _normalise(profile: dict, profile_id: str | None = None) -> dict:
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")
    name = str(profile.get("name") or "Nuevo perfil").strip()[:48]
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "perfil"
    result = dict(profile)
    result["id"] = profile_id or f"{slug}-{uuid.uuid4().hex[:6]}"
    result["name"] = name
    result["description"] = str(profile.get("description") or "")[:160]
    result["builtin"] = False
    result["target_clips"] = max(1, min(15, int(profile.get("target_clips", 5))))
    result["min_seconds"] = max(5, min(175, float(profile.get("min_seconds", 20))))
    result["max_seconds"] = max(
        result["min_seconds"] + 5,
        min(180, float(profile.get("max_seconds", 55))))
    result["layouts"] = [item for item in profile.get("layouts", [])
                         if item in {"split", "screencast", "speaker_cut", "punch_in"}]
    result["output_format"] = (profile.get("output_format")
                               if profile.get("output_format") in
                               {"vertical", "horizontal", "square"} else "vertical")
    result["encoder"] = (profile.get("encoder")
                         if profile.get("encoder") in {"qsv", "auto", "x264", "nvenc"}
                         else "qsv")
    result["whisper_model"] = str(profile.get("whisper_model") or "small")
    result["whisper_language"] = str(profile.get("whisper_language") or "es")
    result["captions"] = bool(profile.get("captions", True))
    result["auto_hook"] = bool(profile.get("auto_hook", True))
    if not isinstance(result.get("caption_style"), dict):
        result["caption_style"] = _caption("#FF2D2D")
    return result


def create_profile(profile: dict) -> dict:
    with _LOCK:
        profiles = _read()
        saved = _normalise(profile)
        profiles.append(saved)
        _write(profiles)
        return saved


def update_profile(profile_id: str, profile: dict) -> dict:
    with _LOCK:
        profiles = _read()
        for index, current in enumerate(profiles):
            if current.get("id") != profile_id:
                continue
            if current.get("builtin"):
                raise PermissionError("Built-in profiles cannot be overwritten; duplicate it first")
            saved = _normalise(profile, profile_id)
            profiles[index] = saved
            _write(profiles)
            return saved
    raise KeyError(profile_id)


def delete_profile(profile_id: str) -> None:
    with _LOCK:
        profiles = _read()
        current = next((p for p in profiles if p.get("id") == profile_id), None)
        if current is None:
            raise KeyError(profile_id)
        if current.get("builtin"):
            raise PermissionError("Built-in profiles cannot be deleted")
        _write([p for p in profiles if p.get("id") != profile_id])
