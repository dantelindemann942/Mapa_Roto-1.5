"""Deterministic offline clip selection used only when the local LLM fails.

Qwen remains the primary editor.  This module is the seat belt: a malformed
JSON response, an Ollama timeout, or an older runtime must not throw away a
Whisper transcript that already took several minutes to produce.
"""
from __future__ import annotations

import math
import re
from typing import Iterable


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalise_segments(transcript: dict, duration: float) -> list[dict]:
    clean = []
    for raw in (transcript or {}).get("segments") or []:
        try:
            start = max(0.0, float(raw.get("start", 0)))
            end = min(float(duration), float(raw.get("end", start)))
        except (TypeError, ValueError):
            continue
        text = _clean_text(raw.get("text"))
        if end > start and text:
            clean.append({"start": start, "end": end, "text": text})
    return sorted(clean, key=lambda item: item["start"])


def _overlap_ratio(a: dict, b: dict) -> float:
    overlap = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    shorter = min(a["end"] - a["start"], b["end"] - b["start"])
    return overlap / shorter if shorter > 0 else 1.0


def _window(segments: list[dict], centre: float, duration: float,
            seconds: float, minimum: float, maximum: float) -> dict | None:
    seconds = min(maximum, max(minimum, seconds, 1.0), duration)
    start = max(0.0, min(centre - seconds / 2, duration - seconds))
    end = min(duration, start + seconds)
    inside = [s for s in segments if s["end"] > start and s["start"] < end]
    if not inside:
        return None

    # Prefer real sentence/segment boundaries while keeping the requested band.
    start = max(0.0, inside[0]["start"] - 0.15)
    end = min(duration, inside[-1]["end"] + 0.25)
    if end - start < minimum:
        missing = minimum - (end - start)
        start = max(0.0, start - missing / 2)
        end = min(duration, start + minimum)
        start = max(0.0, end - minimum)
    if end - start > maximum:
        end = start + maximum

    text = _clean_text(" ".join(s["text"] for s in inside))
    words = text.split()
    if not words:
        return None
    length = max(end - start, 1.0)
    punctuation = sum(text.count(mark) for mark in ("!", "?", "…"))
    # Density finds dialogue-rich stretches; punctuation slightly favours a
    # payoff/question over an arbitrary middle of a sentence.
    raw_score = len(words) / length * 18.0 + punctuation * 3.0
    return {"start": start, "end": end, "text": text, "raw_score": raw_score}


def _copy(candidate: dict, index: int, language: str) -> dict:
    words = candidate["text"].split()
    title = " ".join(words[:12]).strip(" -–—,.;:") or f"Momento {index}"
    if len(words) > 12:
        title += "…"
    spanish = language.lower().startswith("es")
    hook = ("NO VISTE VENIR ESTE MOMENTO" if spanish
            else "YOU DIDN'T SEE THIS COMING")
    description = (
        f"{title} #shorts #maparoto" if spanish
        else f"{title} #shorts #maparoto"
    )
    score = max(45, min(79, int(round(50 + candidate["raw_score"]))))
    return {
        "start": round(candidate["start"], 3),
        "end": round(candidate["end"], 3),
        "predicted_score": score,
        "video_title_for_youtube_short": title[:100],
        "viral_hook_text": hook,
        "video_description_for_tiktok": description,
        "video_description_for_instagram": description,
        "selection_mode": "local_transcript_fallback",
    }


def transcript_clips(transcript: dict, duration: float, min_clips: int,
                     max_clips: int, min_seconds: float,
                     max_seconds: float) -> dict | None:
    """Return spaced dialogue-rich clips without any network/model call."""
    duration = max(0.0, float(duration or 0))
    if duration <= 0:
        return None
    segments = _normalise_segments(transcript, duration)
    if not segments:
        return None

    minimum = min(max(1.0, float(min_seconds)), duration)
    maximum = min(max(minimum, float(max_seconds)), duration)
    target = max(1, min(int(max_clips), max(int(min_clips),
                         min(5, int(math.ceil(duration / 90.0))))))
    target = min(target, max(1, int(duration // max(minimum * 0.8, 1.0))))
    seconds = min(maximum, max(minimum, (minimum + maximum) / 2.0))

    candidates = []
    seen = set()
    for segment in segments:
        centre = (segment["start"] + segment["end"]) / 2
        item = _window(segments, centre, duration, seconds, minimum, maximum)
        if not item:
            continue
        key = round(item["start"], 1)
        if key not in seen:
            seen.add(key)
            candidates.append(item)

    candidates.sort(key=lambda item: item["raw_score"], reverse=True)
    selected = []
    for candidate in candidates:
        if all(_overlap_ratio(candidate, current) <= 0.25 for current in selected):
            selected.append(candidate)
        if len(selected) >= target:
            break

    # Sparse transcripts may not create enough distinct segment-centred
    # candidates.  Uniform centres keep timeline coverage without duplicating.
    if len(selected) < target:
        for index in range(target):
            centre = duration * (index + 0.5) / target
            candidate = _window(segments, centre, duration, seconds, minimum, maximum)
            if candidate and all(_overlap_ratio(candidate, current) <= 0.25
                                 for current in selected):
                selected.append(candidate)
            if len(selected) >= target:
                break

    if not selected:
        return None
    selected.sort(key=lambda item: item["start"])
    language = str((transcript or {}).get("language") or "es")
    shorts = [_copy(item, index, language)
              for index, item in enumerate(selected[:target], 1)]
    return {
        "shorts": shorts,
        "cost_analysis": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "model": "deterministic-local-fallback",
            "local": True,
        },
    }
