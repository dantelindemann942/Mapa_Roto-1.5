"""Local multimodal analysis through Ollama.

MAPA ROTO uses the same Qwen 3.5 model for transcript reasoning and frame
understanding.  Images are sent only to Ollama's loopback API; no frame, audio,
transcript, filename or prompt leaves the computer.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Optional, Sequence, Type

import httpx
from pydantic import BaseModel, Field


DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def base_url() -> str:
    explicit = (os.environ.get("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    llm_url = (os.environ.get("LLM_BASE_URL") or "").strip().rstrip("/")
    if llm_url.endswith("/v1"):
        llm_url = llm_url[:-3]
    return llm_url or DEFAULT_BASE_URL


def model_name() -> str:
    return (os.environ.get("VISION_MODEL") or os.environ.get("LLM_MODEL")
            or DEFAULT_MODEL).strip()


def active() -> bool:
    inferred = "ollama" if ((os.environ.get("OLLAMA_BASE_URL") or "").strip()
                            or (os.environ.get("LLM_PROVIDER") or "").strip().lower()
                            in {"ollama", "local"}) else ""
    provider = (os.environ.get("VISION_PROVIDER") or inferred).strip().lower()
    return provider in {"ollama", "local", "qwen"}


def describe() -> dict:
    return {"provider": "ollama", "model": model_name(), "baseUrl": base_url(),
            "offline": True}


def _timeout() -> float:
    try:
        return float(os.environ.get("VISION_TIMEOUT", "600"))
    except ValueError:
        return 600.0


def _parse_json(text: str) -> dict:
    clean = (text or "").strip()
    if clean.startswith("```"):
        lines = clean.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines.pop()
        clean = "\n".join(lines).strip()
    start, end = clean.find("{"), clean.rfind("}")
    if start >= 0 and end > start:
        clean = clean[start:end + 1]
    parsed = json.loads(clean)
    if not isinstance(parsed, dict):
        raise ValueError("Ollama did not return a JSON object")
    return parsed


def generate_json(prompt: str, frames: Sequence[bytes],
                  schema: Type[BaseModel]) -> dict:
    """Ask the configured Ollama vision model and validate structured output."""
    if not active():
        raise RuntimeError("Local vision is disabled")
    if not frames:
        raise ValueError("At least one frame is required")

    images = [base64.b64encode(frame).decode("ascii") for frame in frames]
    body = {
        "model": model_name(),
        "messages": [{
            "role": "user",
            "content": prompt + "\nResponde únicamente con el objeto JSON solicitado.",
            "images": images,
        }],
        "format": schema.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }
    url = f"{base_url()}/api/chat"
    with httpx.Client(timeout=_timeout()) as client:
        response = client.post(url, json=body)
    if response.status_code >= 400:
        raise RuntimeError(
            f"Ollama vision returned {response.status_code}: {response.text[:300]}")
    payload = response.json()
    text = ((payload.get("message") or {}).get("content") or "").strip()
    return schema.model_validate(_parse_json(text)).model_dump()


def frames_at(video_path: str, times: Sequence[float], width: int = 768) -> list[bytes]:
    """Read JPEG frames at absolute timestamps without decoding the whole video."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    output: list[bytes] = []
    try:
        for timestamp in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(timestamp)) * 1000.0)
            ok, frame = cap.read()
            if not ok:
                continue
            height, frame_width = frame.shape[:2]
            if frame_width <= 0 or height <= 0:
                continue
            scaled_height = max(2, int(height * width / frame_width))
            scaled = cv2.resize(frame, (width, scaled_height),
                                interpolation=cv2.INTER_AREA)
            ok, encoded = cv2.imencode(
                ".jpg", scaled, [cv2.IMWRITE_JPEG_QUALITY, 78])
            if ok:
                output.append(encoded.tobytes())
    finally:
        cap.release()
    return output


class VisualWindowAnswer(BaseModel):
    score: int = Field(ge=0, le=100)
    start_offset: float
    end_offset: float
    reason: str
    viral_hook_text: str
    video_title_for_youtube_short: str
    video_description_for_tiktok: str
    video_description_for_instagram: str


def _window_spans(duration: float, window: float) -> list[tuple[float, float]]:
    if duration <= window:
        return [(0.0, duration)]
    stride = window * 0.72
    starts = []
    cursor = 0.0
    while cursor + 1.0 < duration:
        starts.append(cursor)
        if cursor + window >= duration:
            break
        cursor += stride
    final = max(0.0, duration - window)
    if not starts or abs(starts[-1] - final) > 1.0:
        starts.append(final)
    return [(s, min(duration, s + window)) for s in starts]


def _motion_score(video_path: str, start: float, end: float) -> float:
    """Cheap visual prefilter used only to decide which windows Qwen watches."""
    import cv2
    import numpy as np

    sample_count = 5
    times = [start + (end - start) * (i + 0.5) / sample_count
             for i in range(sample_count)]
    cap = cv2.VideoCapture(video_path)
    previous = None
    values = []
    try:
        for timestamp in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.cvtColor(cv2.resize(frame, (192, 108)), cv2.COLOR_BGR2GRAY)
            if previous is not None:
                values.append(float(np.mean(cv2.absdiff(gray, previous))))
            previous = gray
    finally:
        cap.release()
    return sum(values) / len(values) if values else 0.0


def _shortlist_windows(video_path: str, duration: float, window: float,
                       limit: int) -> list[tuple[float, float]]:
    spans = _window_spans(duration, window)
    scored = [(float(_motion_score(video_path, start, end)), start, end)
              for start, end in spans]
    scored.sort(reverse=True)
    # Greedy spacing stops a single action scene from filling every slot with
    # heavily overlapping windows. Long sources still retain time coverage.
    chosen: list[tuple[float, float]] = []
    for _, start, end in scored:
        midpoint = (start + end) / 2
        if all(abs(midpoint - (a + b) / 2) >= window * 0.45 for a, b in chosen):
            chosen.append((start, end))
        if len(chosen) >= limit:
            break
    if len(chosen) < min(limit, len(spans)):
        for span in spans:
            if span not in chosen:
                chosen.append(span)
            if len(chosen) >= limit:
                break
    return sorted(chosen)


def _normalise_bounds(start: float, end: float, span_duration: float,
                      minimum: float, maximum: float) -> tuple[float, float]:
    start = max(0.0, min(float(start), span_duration))
    end = max(start, min(float(end), span_duration))
    if end - start < minimum:
        centre = (start + end) / 2
        start = max(0.0, centre - minimum / 2)
        end = min(span_duration, start + minimum)
        start = max(0.0, end - minimum)
    if end - start > maximum:
        end = start + maximum
    return start, end


def select_visual_clips(video_path: str, duration: float, language: str,
                        min_clips: int, max_clips: int,
                        min_seconds: float, max_seconds: float) -> Optional[dict]:
    """Pick silent/gameplay moments using motion prefilter + local Qwen vision."""
    if duration <= 0:
        return None
    target = max(1, min(max_clips, max(min_clips, 4)))
    max_windows = max(target, min(8, int(os.environ.get("VISION_MAX_WINDOWS", "6"))))
    window = min(duration, max(36.0, max_seconds * 1.25))
    spans = _shortlist_windows(video_path, duration, window, max_windows)
    candidates = []
    print(f"👁️  Qwen visual local: revisando {len(spans)} ventanas candidatas…")

    for index, (start, end) in enumerate(spans, 1):
        sample_times = [start + (end - start) * (i + 0.5) / 4 for i in range(4)]
        frames = frames_at(video_path, sample_times)
        if not frames:
            continue
        prompt = f"""
Eres editor senior de video corto. Las cuatro imágenes, en orden, resumen una
ventana visual sin diálogo entre {start:.3f}s y {end:.3f}s del video. Evalúa
gameplay, jugadas, movimiento, sorpresa, transformación, humor, tensión y
payoff visual. Ignora cambios triviales de cámara y pantallas estáticas.

Devuelve score 0-100 y el mejor recorte usando start_offset/end_offset relativos
al inicio de ESTA ventana (0 a {end - start:.3f}). Debe durar entre
{min_seconds:g} y {max_seconds:g} segundos y no cortar el payoff. Todo el copy
debe estar en {language or 'español'}: hook máximo 10 palabras, título máximo
100 caracteres y descripciones breves con hashtags relevantes. Si la ventana
es débil, entrega score bajo; no inventes acción que no aparece.
"""
        try:
            answer = generate_json(prompt, frames, VisualWindowAnswer)
        except Exception as exc:
            print(f"   ⚠️ Ventana visual {index} omitida ({exc})")
            continue
        rel_start, rel_end = _normalise_bounds(
            answer["start_offset"], answer["end_offset"], end - start,
            min(min_seconds, end - start), min(max_seconds, end - start))
        candidates.append({
            "start": start + rel_start,
            "end": start + rel_end,
            "predicted_score": int(answer["score"]),
            "video_description_for_tiktok": answer["video_description_for_tiktok"],
            "video_description_for_instagram": answer["video_description_for_instagram"],
            "video_title_for_youtube_short": answer["video_title_for_youtube_short"][:100],
            "viral_hook_text": answer["viral_hook_text"],
            "_reason": answer["reason"],
        })

    candidates.sort(key=lambda item: item["predicted_score"], reverse=True)
    selected = []
    for candidate in candidates:
        overlap = False
        for current in selected:
            intersection = max(0.0, min(candidate["end"], current["end"])
                               - max(candidate["start"], current["start"]))
            shorter = min(candidate["end"] - candidate["start"],
                          current["end"] - current["start"])
            if shorter and intersection / shorter > 0.5:
                overlap = True
                break
        if not overlap:
            candidate.pop("_reason", None)
            selected.append(candidate)
        if len(selected) >= target:
            break

    if not selected and spans:
        # Qwen can time out or reject a schema after OpenCV has already found
        # the most active windows.  Keep those local motion results as a
        # last-resort edit instead of discarding the whole job.  This branch is
        # deliberately lower-confidence and is only reached when every visual
        # model call failed or returned unusable data.
        print("⚠️ Qwen visual no devolvió JSON utilizable; usando las ventanas "
              "de mayor movimiento como respaldo local.")
        for index, (span_start, span_end) in enumerate(spans[:target], 1):
            length = min(max_seconds, max(min_seconds, span_end - span_start))
            centre = (span_start + span_end) / 2
            start = max(0.0, min(centre - length / 2, duration - length))
            end = min(duration, start + length)
            selected.append({
                "start": round(start, 3),
                "end": round(end, 3),
                "predicted_score": 45,
                "video_description_for_tiktok": (
                    f"Momento visual {index} #shorts #maparoto"),
                "video_description_for_instagram": (
                    f"Momento visual {index} #shorts #maparoto"),
                "video_title_for_youtube_short": f"Momento visual {index}",
                "viral_hook_text": "MIRA LO QUE PASA AQUÍ",
                "selection_mode": "local_motion_fallback",
            })

    if not selected:
        return None
    return {
        "shorts": selected,
        "cost_analysis": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "model": model_name(),
            "local": True,
        },
    }
