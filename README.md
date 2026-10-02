# MAPA ROTO Clip

Aplicación de escritorio para Windows que convierte videos largos en clips
verticales usando IA local. Es un fork del núcleo MIT de
[OpenShorts](https://github.com/mutonby/openshorts), con interfaz propia y una
ruta de compilación automatizada a `.exe`.

> Estado: **v0.1.5 funcional / beta técnica**. El flujo principal, la cola,
> perfiles, historial, exportación ZIP, visión local y empaquetado Windows están
> implementados. Antes de usarlo con material irreemplazable, prueba un video
> corto y conserva siempre el original.

## Qué queda local

| Etapa | Motor |
|---|---|
| Transcripción y palabras | Faster-Whisper `small`, CPU int8, español |
| Selección de momentos con diálogo | Ollama + `qwen3.5:4b` |
| Gameplay / escenas sin diálogo | Movimiento OpenCV + visión de `qwen3.5:4b` |
| Layout y hook visual | `qwen3.5:4b` multimodal |
| Rostros y personas | MediaPipe + YOLOv8n |
| Reencuadre | OpenShorts v2, 9:16 / 1:1 / horizontal |
| Render | FFmpeg; Intel Quick Sync `h264_qsv` con fallback x264 |
| Subtítulos | ASS karaoke MAPA ROTO, perfiles editables |
| Estado | Archivos JSON/locales; no requiere cuenta ni base externa |

En el flujo de escritorio predeterminado ningún video, audio, transcript o
fotograma se envía a un proveedor remoto. Ollama escucha sólo en `127.0.0.1`.
Tras descargar los modelos una vez, el uso normal funciona sin Internet.

## Equipo objetivo

Configuración diseñada para un notebook Intel Core i7 de 13.ª generación con
16 GB de RAM:

- un trabajo y un render de clip a la vez;
- Qwen 3.5 4B Q4 (~3,4 GB) como único LLM/VLM;
- Whisper Small CPU int8;
- YOLOv8n y MediaPipe en CPU;
- Quick Sync para codificación H.264 cuando el driver Intel lo permite.

La aplicación prueba Quick Sync antes de usarlo. Si falla, conserva el trabajo y
renderiza con `libx264`; sólo será más lento.

## Uso como código fuente

Requisitos: Windows 10/11 x64, Python 3.11, Node.js 24, FFmpeg y
[Ollama para Windows](https://ollama.com/download/windows).

```powershell
git clone <TU-FORK> mapa-roto-clip
cd mapa-roto-clip
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-desktop.txt

cd local-ui
npm ci
npm run build
cd ..

Copy-Item .env.mapa-roto.example .env
ollama pull qwen3.5:4b
python desktop.py
```

En la primera ejecución abre **Sistema local → Preparar modelos**. Esa acción
descarga/verifica Qwen, YOLOv8n y Faster-Whisper. Cuando todas las tarjetas
quedan verdes, puedes desconectar Internet.

## Compilar el instalador `.exe`

Instala además [Inno Setup 6](https://jrsoftware.org/isdl.php) y ejecuta:

```powershell
.\scripts\build_windows.ps1 -Version 0.1.5
```

El script:

1. compila la interfaz React;
2. instala dependencias de build;
3. incorpora `ffmpeg.exe` y `ffprobe.exe` con Quick Sync;
4. crea el ejecutable con PyInstaller;
5. ejecuta un smoke test del binario;
6. genera `release\MAPA-ROTO-Clip-Setup-0.1.5.exe`.

El instalador contiene la aplicación, runtime Python y FFmpeg. No contiene los
pesos de IA: eso evita un instalador de varios GB y no mezcla licencias de
modelos. La preparación inicial los deja en el perfil local del usuario para
ejecuciones posteriores offline.

Desde v0.1.1 el ejecutable gráfico redirige sus diagnósticos a
`%LOCALAPPDATA%\MAPA ROTO Clip\logs\desktop.log`. Esto evita que el arranque de
Uvicorn dependa de una consola de Windows y permite revisar fallos posteriores.

Desde v0.1.2 el paquete conserva `torch.distributed`, requerido indirectamente
por Ultralytics, y el self-test del `.exe` importa la pila local completa antes
de generar el instalador. La preparación ejecuta Qwen, YOLO y Faster-Whisper
como etapas independientes con reintentos: repetirla conserva lo ya descargado.

Desde v0.1.3 también se conserva `torch.testing`, requerido por
`torch.autograd.gradcheck` durante la importación de PyTorch 2.11. Una prueba de
empaquetado impide excluir nuevamente estos módulos base.

Desde v0.1.4 cada trabajo guarda `pipeline.log`, `failure.json` y, ante una
excepción no controlada, `worker-crash.log` dentro de su carpeta de salida. La
cola muestra el error real, permite desplegar el registro y ofrece
**Descargar diagnóstico**. También se fijó `lap==0.5.13` para que Ultralytics no
intente instalarlo durante el uso offline. Ollama usa su API nativa con esquema
JSON y pensamiento desactivado; si Qwen no entrega una respuesta válida, la
aplicación conserva el trabajo mediante un selector determinista local basado
en la transcripción o el movimiento visual.

## Compilar desde GitHub Actions

### Corrección de entrega en Windows — 0.1.5

Esta versión corrige el caso «Clip 1…5 ready / Process finished successfully»
seguido de un trabajo fallido sin clips. Las capturas demuestran que el render
terminó; sin el diagnóstico original no es posible distinguir con certeza
entre nombre/ruta rechazados o un marcador dañado. La corrección cubre ambos:

- Los archivos subidos usan nombres de salida seguros y cortos; en el desktop
  el título se limita a 64 bytes para no superar rutas clásicas de Windows.
- Los corchetes se tratan como texto literal al buscar versiones con subtítulos.
- El worker fuerza UTF-8 y vacía los marcadores; guarda además `rendered_file`
  en los metadatos, incluso cuando no hay hook.
- Un marcador inexistente ya no oculta un archivo válido. Solo se aceptan
  archivos no vacíos dentro de la carpeta del trabajo; no se inventan clips.
- La recuperación al reiniciar comprueba el disco y admite consultas a rutas
  antiguas largas en Windows. Antes de reprocesar, revisa **Historial** y
  **Abrir carpeta de salida**, sin borrar tus proyectos ni modelos.
- FFprobe y el lanzamiento del worker usan `stdin` explícito, evitando heredar
  un handle de entrada inválido al ejecutar sin consola.
- **Descargar diagnóstico** incluye nombres/tamaños de archivos y errores de
  consulta de disco, además de los registros del pipeline.

El build ahora prueba un worker **sin consola**: genera un MP4 sintético,
consulta FFprobe, aplica hook y subtítulos, resuelve el archivo final y verifica
UTF-8. No necesita descargar modelos ni procesar tus videos. La prueba usa
CPU porque GitHub no tiene tu iGPU Intel: Quick Sync y la inferencia completa
deben comprobarse en el notebook objetivo.

Para actualizar: cierra la app, reemplaza los archivos del repositorio por los
de este ZIP (incluyendo `.github`), ejecuta **Windows EXE** con versión `0.1.5`
y descarga **mapa-roto-clip-windows**. Instala encima; no borres
`%LOCALAPPDATA%\MAPA ROTO Clip`. Prueba primero un video propio de 1–2 minutos.

El workflow **Windows EXE** se puede lanzar manualmente en la pestaña Actions.
También se ejecuta con una etiqueta:

```bash
git tag v0.1.5
git push origin v0.1.5
```

El `.exe` queda como artifact descargable del workflow. No se publica una
Release automáticamente: revisa primero `THIRD_PARTY_NOTICES.md` y las licencias
recopiladas dentro de `dist\MapaRotoClip`.

La secuencia completa de publicación, build y preparación del notebook está en
[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).

## Flujo de la aplicación

1. Arrastra uno o varios videos.
2. Elige un perfil: MAPA ROTO, Gameplay, Podcast o Tutorial/Pantalla.
3. La cola procesa las fuentes de una en una.
4. Cada trabajo muestra clips apenas están listos.
5. Descarga un ZIP por fuente o un ZIP global de todo el lote.
6. El historial se reconstruye desde disco y sobrevive a reinicios.

Los perfiles guardan cantidad/duración, layouts, encoder, modelo Whisper y el
look completo del subtítulo. Los perfiles base son inmutables; se duplican para
crear variantes propias.

## Variables principales

Consulta [`.env.mapa-roto.example`](.env.mapa-roto.example). Las más útiles:

```dotenv
LLM_MODEL=qwen3.5:4b
VISION_MODEL=qwen3.5:4b
WHISPER_MODEL=small
WHISPER_LANGUAGE=es
FFMPEG_ENCODER=qsv
MAX_CONCURRENT_JOBS=1
CLIP_WORKERS=1
```

Para videos mixtos español/inglés usa `WHISPER_LANGUAGE=auto`. En este equipo no
se recomienda subir a Whisper Medium mientras Qwen esté residente salvo que se
acepten tiempos y consumo mayores.

## Privacidad y red

- La interfaz y API se enlazan exclusivamente a `127.0.0.1`.
- La ingestión por URL está desactivada en el escritorio; se trabaja con
  archivos locales cuyos derechos confirma el usuario.
- Algunas rutas compatibles con Gemini siguen en el núcleo heredado, pero la
  interfaz MAPA ROTO no las invoca ni necesita una clave con la configuración
  predeterminada.
- Los únicos accesos de red esperados son durante la instalación de dependencias
  y la descarga inicial de modelos.

## Pruebas

```powershell
python -m pytest tests/test_local_vision.py tests/test_local_profiles.py `
  tests/test_ffmpeg_utils.py tests/test_subtitles.py -q
cd local-ui
npm run build
```

## Licencias y atribución

El núcleo incluido es MIT, copyright 2024 OpenShorts. Este fork conserva
[LICENSE](LICENSE) y la atribución. El directorio comercial `cloud/` de upstream
fue retirado por completo; MAPA ROTO Clip no activa billing, SaaS, publicación
social ni servicios cloud de OpenShorts.

Qwen 3.5 se descarga por Ollama bajo Apache 2.0. La dependencia Ultralytics y
sus modelos se ofrecen bajo AGPL-3.0 o licencia Enterprise. Quien publique el
binario debe cumplir las obligaciones de código fuente correspondiente; un
producto cerrado/comercial debe sustituirla o adquirir la licencia adecuada.
El FFmpeg descargado por el build incorpora componentes GPL. Lee
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) antes de distribuir el `.exe`.

## Créditos

- Núcleo y algoritmo de reencuadre: [OpenShorts](https://github.com/mutonby/openshorts)
- Inferencia local: [Ollama](https://ollama.com/)
- Modelo multimodal: Qwen 3.5 4B
- Transcripción: faster-whisper / CTranslate2
- Video: FFmpeg
