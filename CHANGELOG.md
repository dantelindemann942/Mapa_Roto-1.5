# Changelog

## 0.1.5 - 2026-10-02

### Corregido

- Entrega de clips en Windows: nombres cortos para subidas locales, patrones
  con corchetes literales, fallback de marcador inválido y `rendered_file`
  persistido en metadatos mediante reemplazo atómico.
- El worker configura UTF-8 explícito y publicación inmediata de `CLIP_READY`.
- Entrada del worker y de FFprobe redirigida explícitamente para uso sin consola.
- Recuperación al reiniciar basada en archivos reales, sin proyectos fantasma;
  consultas a rutas largas de proyectos antiguos en Windows.
- Diagnóstico con inventario de archivos/tamaños y errores de acceso al disco;
  lectura de colas de log con memoria limitada.
- Build detiene errores de comandos externos y comprueba un worker sin consola
  con FFmpeg, FFprobe, hook, subtítulos y entrega de un MP4 sintético.

### Validación

- Pruebas de regresión para cinco clips terminados, marcadores con codificación
  dañada, tildes, corchetes, recuperación y rechazo de rutas externas.
- Render sintético real y build de interfaz validados en Linux.
- 663 pruebas aprobadas; 20 omitidas por dependencias opcionales/no instaladas
  en este entorno. No equivale a inferencia completa validada en Windows.
- El instalador Windows y Quick Sync requieren la ejecución de GitHub Actions
  y comprobación en el notebook; no se simula que esa validación ya ocurrió.

## 0.1.4 - 2026-09-30

### Corregido

- El worker espera a vaciar `stdout/stderr` antes de cerrar el trabajo, evitando
  que `Process failed with exit code 1` oculte la excepción real.
- Cada trabajo local conserva `pipeline.log`, `failure.json` y, si el proceso
  se cae fuera del flujo normal, `worker-crash.log`.
- La cola muestra el motivo útil, permite revisar el registro completo y
  descargar un diagnóstico de texto desde la propia aplicación.
- Ollama/Qwen usa `/api/chat` con esquema JSON y `think=false`; conserva una
  compatibilidad automática para versiones antiguas de Ollama.
- Si Qwen no entrega JSON válido, el procesamiento continúa con selección
  determinista local basada en transcripción o movimiento visual.
- `lap==0.5.13` queda fijado, incluido por PyInstaller y comprobado por el
  auto-test, evitando instalaciones automáticas durante el uso offline.
- Los workflows usan las acciones oficiales v7 sobre runtime Node 24.

### Validación

- 655 pruebas aprobadas y 20 omitidas por diseño.
- Build de producción de la interfaz Vite aprobado con Node.js 24.
