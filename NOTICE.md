# Notices

MAPA ROTO Clip is a modified distribution of the MIT-licensed OpenShorts core.

- Original project: https://github.com/mutonby/openshorts
- Original copyright: Copyright (c) 2024 OpenShorts
- Local desktop adaptations and MAPA ROTO interface: 2026 MAPA ROTO contributors

Upstream's separately licensed `cloud/` directory and its billing/SaaS
dependencies are intentionally not distributed in this fork. The included
OpenShorts core remains under the root MIT `LICENSE`; the desktop runtime also
forces `BILLING_ENABLED=0`.

The installer may contain third-party runtime components including Python,
PyTorch, FFmpeg, MediaPipe, Ultralytics, lap, faster-whisper, CTranslate2, pywebview
and their dependencies. Their copyright and license terms continue to apply.
AI model weights are not distributed inside this repository or installer;
Ollama downloads them at the user's request from their respective registries.
See `THIRD_PARTY_NOTICES.md` before publishing a binary distribution.
