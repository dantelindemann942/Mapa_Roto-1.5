"""Offline delivery smoke test; no downloaded models or user videos needed."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


UTF8_SENTINEL = "SMOKE_UTF8 dimensión, español, corazón ✓"


def run_smoke() -> None:
    from app import _clips_actually_rendered
    from hooks import add_hook_to_video
    from subtitles import burn_subtitles, generate_ass

    previous_encoder = os.environ.get("FFMPEG_ENCODER")
    os.environ["FFMPEG_ENCODER"] = "x264"  # CI has no Intel GPU.
    try:
        with tempfile.TemporaryDirectory(prefix="mapa-smoke-") as folder:
            root = Path(folder)
            stem = "Prueba_dimensión_[Rick]"
            clean = root / f"{stem}_clip_1.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                 "color=c=navy:s=320x568:r=10:d=0.6", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", str(clean)],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, check=True, timeout=60)
            dimensions = subprocess.check_output(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
                 str(clean)], stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=30).decode("utf-8").strip()
            if dimensions != "320x568":
                raise RuntimeError(f"Packaged FFprobe returned {dimensions!r}")
            hooked = root / f"hooked_1_{clean.name}"
            add_hook_to_video(str(clean), "Prueba en español", str(hooked), duration=0.5)
            ass = root / "subs.ass"
            transcript = {"segments": [{"start": 0, "end": 0.6, "text": "Hola",
                           "words": [{"word": "Hola", "start": 0, "end": 0.5}]}]}
            if not generate_ass(transcript, 0, 0.6, str(ass)):
                raise RuntimeError("Packaged captions could not be generated")
            final = root / f"subtitled_2_{hooked.name}"
            burn_subtitles(str(hooked), str(ass), str(final))
            # Round-trip metadata exactly as the real worker/API do.
            data = {"shorts": [{"start": 0, "end": 0.6,
                                 "rendered_file": final.name}]}
            meta = root / f"{stem}_metadata.json"
            meta.write_text(json.dumps(data), encoding="utf-8")
            clips = json.loads(meta.read_text(encoding="utf-8"))["shorts"]
            rendered, missing = _clips_actually_rendered(
                "packaged-smoke", folder, stem, clips)
            if missing or len(rendered) != 1 or not rendered[0]["video_url"].endswith(final.name):
                raise RuntimeError("Packaged clip delivery did not select the final captioned MP4")
            final_probe = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(final)],
                stdin=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
            if float(final_probe) <= 0:
                raise RuntimeError("Packaged final video has no duration")
        print(UTF8_SENTINEL, flush=True)
        print("Packaged FFmpeg + FFprobe + hooks + captions + delivery OK", flush=True)
    finally:
        if previous_encoder is None:
            os.environ.pop("FFMPEG_ENCODER", None)
        else:
            os.environ["FFMPEG_ENCODER"] = previous_encoder
