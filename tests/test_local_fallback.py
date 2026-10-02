import local_fallback


def _transcript(seconds=240):
    segments = []
    for start in range(0, seconds, 6):
        segments.append({
            "start": float(start),
            "end": float(start + 5),
            "text": f"Esta es una frase importante número {start}. ¿Qué pasará ahora?",
        })
    return {"language": "es", "segments": segments}


def test_transcript_fallback_returns_spaced_valid_clips():
    result = local_fallback.transcript_clips(
        _transcript(), 240, min_clips=3, max_clips=5,
        min_seconds=20, max_seconds=45)

    assert result and len(result["shorts"]) >= 3
    for clip in result["shorts"]:
        assert 0 <= clip["start"] < clip["end"] <= 240
        assert 20 <= clip["end"] - clip["start"] <= 45
        assert clip["selection_mode"] == "local_transcript_fallback"
        assert clip["viral_hook_text"] == "NO VISTE VENIR ESTE MOMENTO"


def test_transcript_fallback_refuses_empty_transcript():
    assert local_fallback.transcript_clips(
        {"language": "es", "segments": []}, 240, 3, 5, 20, 45) is None


def test_transcript_fallback_handles_short_valid_source():
    result = local_fallback.transcript_clips(
        _transcript(60), 60, min_clips=5, max_clips=8,
        min_seconds=20, max_seconds=55)
    assert result
    assert all(clip["end"] <= 60 for clip in result["shorts"])
