# Checklist: GitHub → instalador Windows

## 1. Publicar el código

Desde la carpeta descomprimida:

```powershell
git init
git add .
git commit -m "fix: MAPA ROTO Clip v0.1.5 diagnostics and local fallbacks"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/mapa-roto-clip.git
git push -u origin main
```

Antes de `git add`, confirma que no existan `.env`, videos, modelos `.pt`,
`local-data/`, `output/`, `dist/` ni `vendor/ffmpeg/`. El `.gitignore` ya los
excluye, pero `git status --short` es la verificación final.

## 2. Validar el fork

En GitHub abre **Actions → CI**. Deben quedar verdes:

- pruebas Python del núcleo local;
- build de la interfaz `local-ui`.

## 3. Compilar el `.exe`

Abre **Actions → Windows EXE → Run workflow**. El job construye:

```text
release/MAPA-ROTO-Clip-Setup-0.1.5-dev.exe
```

Al terminar, descarga el artifact **mapa-roto-clip-windows**. También puedes
compilar en una máquina Windows con:

```powershell
.\scripts\build_windows.ps1 -Version 0.1.5
```

La compilación local requiere Python 3.11, Node.js 24 e Inno Setup 6. El script
descarga FFmpeg, genera el icono, crea los dos ejecutables internos
(`MapaRotoClip.exe` y `MapaRotoWorker.exe`), ejecuta su autoevaluación y produce
un único instalador.

## 4. Preparar el notebook objetivo

1. Instala [Ollama para Windows](https://ollama.com/download/windows) y déjalo iniciado.
2. Instala **MAPA ROTO Clip**.
3. Abre **Sistema local → Preparar modelos** con Internet una sola vez.
4. Espera que Qwen, Faster-Whisper, YOLO y MediaPipe aparezcan listos.
5. Procesa un video corto de prueba.
6. Desconecta Internet y repite el trabajo para validar el modo offline.

Si Intel Quick Sync no está disponible, actualiza el driver gráfico Intel. La
aplicación seguirá funcionando con `libx264`, aunque el render será más lento.

## 5. Antes de distribuir públicamente

- Lee `THIRD_PARTY_NOTICES.md`.
- Conserva `LICENSE`, `NOTICE.md`, `fonts/OFL.txt` y los avisos recopilados en
  el instalador.
- Cumple AGPL-3.0/Enterprise para Ultralytics y GPLv3 para el build estático de
  FFmpeg; publica el código fuente correspondiente cuando aplique.
- Firma digitalmente el instalador si lo distribuirás fuera de tu propio
  equipo; este proyecto no incluye un certificado de firma.
- Prueba el instalador en un Windows 10/11 x64 limpio antes de etiquetar una
  versión estable.
