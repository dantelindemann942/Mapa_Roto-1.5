# Third-party notices

MAPA ROTO Clip combines independent open-source projects. The root MIT license
covers the included OpenShorts-derived source; it does **not** replace the
licenses of these dependencies or downloaded model weights.

This file is an operational checklist, not legal advice. Before publishing an
installer, preserve the license files emitted by the exact dependency versions
and review the resulting PyInstaller distribution.

## Components with distribution implications

| Component | How it is used | License / action |
|---|---|---|
| Ultralytics + YOLOv8n | Local person/object detection and tracking | Ultralytics offers AGPL-3.0 or an Enterprise license. A distributor choosing AGPL must ensure the complete corresponding source is offered; publishing this repository alone may not satisfy every obligation. A closed/proprietary product should obtain the Enterprise license or replace this dependency. https://docs.ultralytics.com/#yolo-licenses-how-is-ultralytics-yolo-licensed |
| lap 0.5.13 | Linear-assignment runtime used by Ultralytics tracking | BSD-2-Clause. Preserve the package's bundled LICENSE when redistributing the installer. https://pypi.org/project/lap/0.5.13/ |
| FFmpeg build from gyan.dev | Separate `ffmpeg.exe` / `ffprobe.exe` programs used for decode, filters and H.264 rendering | FFmpeg is LGPL-2.1-or-later by default, but GPL applies when GPL parts such as libx264 are enabled. The current essentials build is treated as GPL-capable; preserve its included license/readme and provide the exact corresponding FFmpeg source when redistributing. https://ffmpeg.org/legal.html |
| Qwen 3.5 4B | Multimodal reasoning through Ollama; weights downloaded by the user | Apache License 2.0 according to the Ollama model registry. The weights are not bundled in this repository or installer. https://ollama.com/library/qwen3.5:4b |
| Anton and Noto Serif fonts | Burned subtitles and hook typography | SIL Open Font License 1.1. Copyright notices and license text are bundled in `fonts/OFL.txt`. |

## Principal runtime projects

The installer can also contain Python, PyTorch, torchvision, MediaPipe,
faster-whisper, CTranslate2, OpenCV, lap, PySceneDetect, yt-dlp, FastAPI, Uvicorn,
pywebview, React, Vite, Lucide, Pillow, httpx and their transitive dependencies.
Each keeps its own copyright and license. PyInstaller normally collects package
metadata, but binary distributors remain responsible for carrying the notices
required by the versions actually resolved during the build.

## Source availability

- MAPA ROTO/OpenShorts-derived source: distribute this repository at the same
  version as the installer.
- Python/Node dependency versions: `requirements*.txt` and the npm lockfile.
- FFmpeg build provenance: `scripts/fetch_ffmpeg.ps1`; retain the downloaded
  build's `LICENSE.txt` and `README.txt` inside the installer.
- Model provenance: `model_setup.py`; weights are downloaded only after the
  user explicitly selects **Preparar modelos**.

Do not add API keys, model weights, user media, `local-data/`, `output/`, or
generated profiles/history to a source release.
