import local_vision


def test_ollama_url_is_derived_from_openai_compatible_url(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    assert local_vision.base_url() == "http://127.0.0.1:11434"


def test_local_vision_requires_explicit_local_configuration(monkeypatch):
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert local_vision.active() is False
    monkeypatch.setenv("VISION_PROVIDER", "ollama")
    assert local_vision.active() is True


def test_visual_selector_returns_valid_non_overlapping_clips(monkeypatch):
    monkeypatch.setattr(local_vision, "_motion_score", lambda *args: 5.0)
    monkeypatch.setattr(local_vision, "frames_at", lambda *args, **kwargs: [b"jpg"] * 4)
    answers = iter([
        {"score": 93, "start_offset": 2, "end_offset": 24, "reason": "jugada",
         "viral_hook_text": "La jugada imposible", "video_title_for_youtube_short": "Jugada",
         "video_description_for_tiktok": "Mira esto #gaming",
         "video_description_for_instagram": "Mira esto #gaming"},
        {"score": 82, "start_offset": 8, "end_offset": 31, "reason": "payoff",
         "viral_hook_text": "Nadie esperaba esto", "video_title_for_youtube_short": "Payoff",
         "video_description_for_tiktok": "Final #gaming",
         "video_description_for_instagram": "Final #gaming"},
        {"score": 20, "start_offset": 0, "end_offset": 20, "reason": "débil",
         "viral_hook_text": "Momento", "video_title_for_youtube_short": "Momento",
         "video_description_for_tiktok": "Video",
         "video_description_for_instagram": "Video"},
    ])
    monkeypatch.setattr(local_vision, "generate_json", lambda *args, **kwargs: next(answers))
    monkeypatch.setenv("VISION_MAX_WINDOWS", "3")

    result = local_vision.select_visual_clips(
        "source.mp4", 180, "español", 2, 2, 15, 45)

    assert result["cost_analysis"]["local"] is True
    assert len(result["shorts"]) == 2
    assert result["shorts"][0]["predicted_score"] >= result["shorts"][1]["predicted_score"]
    assert all(15 <= clip["end"] - clip["start"] <= 45 for clip in result["shorts"])


def test_bounds_are_expanded_and_clamped():
    start, end = local_vision._normalise_bounds(19, 20, 20, 15, 40)
    assert start == 5
    assert end == 20


def test_visual_selector_keeps_motion_fallback_when_qwen_fails(monkeypatch):
    monkeypatch.setattr(local_vision, "_motion_score", lambda *args: 8.0)
    monkeypatch.setattr(local_vision, "frames_at", lambda *args, **kwargs: [b"jpg"] * 4)
    monkeypatch.setattr(
        local_vision, "generate_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("invalid JSON")))
    monkeypatch.setenv("VISION_MAX_WINDOWS", "3")

    result = local_vision.select_visual_clips(
        "source.mp4", 180, "español", 2, 2, 15, 45)

    assert result and len(result["shorts"]) == 2
    assert all(clip["selection_mode"] == "local_motion_fallback"
               for clip in result["shorts"])
