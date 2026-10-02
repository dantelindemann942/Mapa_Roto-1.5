# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path.cwd()
datas = [
    (str(root / "local-ui" / "dist"), "local-ui/dist"),
    (str(root / "fonts"), "fonts"),
    (str(root / "assets"), "assets"),
    (str(root / "LICENSE"), "."),
    (str(root / "NOTICE.md"), "."),
    (str(root / "THIRD_PARTY_NOTICES.md"), "."),
]
binaries = []
for executable in ("ffmpeg.exe", "ffprobe.exe"):
    path = root / "vendor" / "ffmpeg" / "bin" / executable
    if path.exists():
        binaries.append((str(path), "vendor/ffmpeg/bin"))
for notice in ("LICENSE.txt", "README.txt"):
    path = root / "vendor" / "ffmpeg" / notice
    if path.exists():
        datas.append((str(path), "vendor/ffmpeg"))

hiddenimports = [
    "main", "model_setup", "packaged_smoke",
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on",
    "webview.platforms.edgechromium", "multipart", "email_validator",
    "torch.distributed", "torch.testing", "torch.testing._comparison",
    "faster_whisper", "ctranslate2", "av", "huggingface_hub",
    "ultralytics", "lap", "mediapipe", "scenedetect", "yt_dlp",
    "google.genai", "google.genai.types",
]

# These packages carry runtime data files that PyInstaller cannot infer from
# dynamic imports. Torch/OpenCV use their maintained PyInstaller hooks.
for package in ("faster_whisper", "ctranslate2", "av", "ultralytics", "lap",
                "mediapipe", "transnetv2_pytorch", "py3langid",
                "scenedetect", "yt_dlp", "webview", "google.genai"):
    try:
        package_datas, package_bins, package_hidden = collect_all(package)
        datas += package_datas
        binaries += package_bins
        hiddenimports += package_hidden
    except Exception:
        pass

a = Analysis(
    [str(root / "desktop.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # torch.distributed and torch.testing are runtime dependencies.  Do not
    # exclude them: torch.utils.data and torch.autograd.gradcheck import them
    # while Ultralytics initializes inside the packaged executable.
    excludes=[
        "cloud", "alembic", "sqlalchemy", "pytest", "IPython", "jupyter",
        "matplotlib.tests",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

icon_path = root / "packaging" / "mapa-roto.ico"
gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MapaRotoClip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon_path) if icon_path.exists() else None,
)
worker_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MapaRotoWorker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=str(icon_path) if icon_path.exists() else None,
)
coll = COLLECT(
    gui_exe,
    worker_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MapaRotoClip",
)
