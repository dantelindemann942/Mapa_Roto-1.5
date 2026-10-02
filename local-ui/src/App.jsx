import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle, Captions, Check, CheckCircle2, ChevronRight, Clock3, Copy,
  Cpu, Download, Eye, Film, FolderOpen, HardDrive, History, Layers3, Loader2,
  MonitorPlay, Plus, RefreshCw, Scissors, Settings2, SlidersHorizontal,
  Sparkles, UploadCloud, WifiOff, X, Zap,
} from 'lucide-react'

const NAV = [
  ['studio', Scissors, 'Crear clips'],
  ['queue', Layers3, 'Cola de trabajo'],
  ['history', History, 'Historial'],
  ['profiles', SlidersHorizontal, 'Perfiles'],
  ['system', Cpu, 'Sistema local'],
]

const asJson = (response) => response.ok
  ? response.json()
  : response.json().catch(() => ({})).then((body) => {
      const detail = typeof body.detail === 'string' ? body.detail : body.detail?.message
      return Promise.reject(new Error(detail || `Error ${response.status}`))
    })

const request = (url, options) => fetch(url, options).then(asJson)
const statusLabel = { queued: 'En cola', processing: 'Procesando', completed: 'Completado', failed: 'Falló' }
const savedJobs = () => {
  try {
    const value = JSON.parse(localStorage.getItem('mapa-roto-jobs') || '[]')
    return Array.isArray(value) ? value : []
  } catch {
    return []
  }
}

function Brand() {
  return <div className="brand">
    <div className="brand-mark"><span>M</span><i /></div>
    <div><strong>MAPA ROTO</strong><small>CLIP · LOCAL</small></div>
  </div>
}

function Sidebar({ page, setPage, queueCount }) {
  return <aside className="sidebar">
    <Brand />
    <nav>
      {NAV.map(([id, Icon, label]) => <button key={id} className={page === id ? 'active' : ''} onClick={() => setPage(id)}>
        <Icon size={18} /><span>{label}</span>{id === 'queue' && queueCount > 0 && <b>{queueCount}</b>}
      </button>)}
    </nav>
    <div className="privacy-card">
      <span className="live-dot" /><strong>100% LOCAL</strong>
      <p>Video, audio y texto se procesan en este equipo.</p>
      <div><WifiOff size={14} /> Sin nube</div>
    </div>
    <footer>Núcleo OpenShorts · avisos de terceros</footer>
  </aside>
}

function Header({ page, system }) {
  const item = NAV.find(([id]) => id === page)
  return <header className="topbar">
    <div><span className="eyebrow">ESTUDIO OFFLINE</span><h1>{item?.[2]}</h1></div>
    <div className={`system-pill ${system?.ready ? 'ready' : ''}`}>
      <span /><div><strong>{system?.ready ? 'Motor listo' : 'Revisar sistema'}</strong><small>{system?.ready ? 'Qwen · Whisper · procesamiento local' : 'Falta uno o más componentes'}</small></div>
    </div>
  </header>
}

function DropZone({ files, setFiles }) {
  const input = useRef(null)
  const add = (list) => {
    const videos = [...list].filter((file) => file.type.startsWith('video/') || /\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(file.name))
    setFiles((current) => [...current, ...videos].filter((file, index, all) => all.findIndex((other) => other.name === file.name && other.size === file.size) === index))
  }
  return <>
    <div className="drop-zone" onClick={() => input.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); add(event.dataTransfer.files) }}>
      <input ref={input} type="file" accept="video/*,.mkv" multiple hidden onChange={(event) => add(event.target.files)} />
      <div className="upload-orbit"><UploadCloud size={30} /></div>
      <h3>Arrastra tus videos aquí</h3>
      <p>o haz clic para buscar · MP4, MOV, MKV, WebM</p>
      <span>Hasta 2 GB por archivo</span>
    </div>
    {files.length > 0 && <div className="file-list">
      {files.map((file, index) => <div className="file-row" key={`${file.name}-${file.size}`}>
        <div className="file-icon"><Film size={18} /></div><div><strong>{file.name}</strong><small>{(file.size / 1024 / 1024).toFixed(1)} MB</small></div>
        <button className="icon-button" onClick={() => setFiles((all) => all.filter((_, i) => i !== index))}><X size={16} /></button>
      </div>)}
    </div>}
  </>
}

function ProfileStrip({ profiles, selected, setSelected }) {
  return <div className="profile-strip">
    {profiles.map((profile) => <button key={profile.id} className={selected === profile.id ? 'selected' : ''} style={{ '--accent': profile.accent }} onClick={() => setSelected(profile.id)}>
      <span className="profile-swatch" /><div><strong>{profile.name}</strong><small>{profile.target_clips} clips · {profile.min_seconds}–{profile.max_seconds}s</small></div>{selected === profile.id && <Check size={16} />}
    </button>)}
  </div>
}

function Studio({ profiles, onSubmit, busy, systemReady, onOpenSystem }) {
  const [files, setFiles] = useState([])
  const [profileId, setProfileId] = useState('mapa-roto')
  const profile = profiles.find((item) => item.id === profileId) || profiles[0]
  const [rights, setRights] = useState(true)
  const submit = async () => {
    if (!files.length || !profile || !rights) return
    await onSubmit(files, profile)
    setFiles([])
  }
  return <div className="page-grid studio-grid">
    <section className="panel primary-panel">
      <div className="section-heading"><div><span>01</span><h2>Material fuente</h2></div><small>{files.length ? `${files.length} archivo${files.length > 1 ? 's' : ''}` : 'Lote múltiple habilitado'}</small></div>
      <DropZone files={files} setFiles={setFiles} />
    </section>
    <section className="panel">
      <div className="section-heading"><div><span>02</span><h2>Perfil de edición</h2></div><small>Tu receta reutilizable</small></div>
      <ProfileStrip profiles={profiles} selected={profileId} setSelected={setProfileId} />
      {profile && <div className="profile-summary">
        <div><Captions size={17} /><span>Subtítulo</span><strong style={{ color: profile.caption_style?.highlight_color }}>{profile.caption_style?.highlight_color}</strong></div>
        <div><Eye size={17} /><span>Layouts</span><strong>{profile.layouts?.length || 0} activos</strong></div>
        <div><Cpu size={17} /><span>Encoder</span><strong>{profile.encoder?.toUpperCase()}</strong></div>
        <div><Sparkles size={17} /><span>IA</span><strong>Qwen local</strong></div>
      </div>}
    </section>
    <section className="panel launch-panel">
      {!systemReady && <button className="engine-warning" onClick={onOpenSystem}><AlertTriangle size={17} /><span><strong>Motor local aún no está preparado</strong><small>Instala/verifica Qwen, Whisper y YOLO antes de crear clips.</small></span><ChevronRight size={17} /></button>}
      <label className="rights"><input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} /><span><Check size={13} /></span>Confirmo que tengo derechos para procesar este material.</label>
      <div className="launch-copy"><Zap size={22} /><div><strong>{files.length || 0} fuente{files.length === 1 ? '' : 's'} · {files.length * (profile?.target_clips || 0)} clips objetivo</strong><small>Se procesarán de a uno para cuidar los 16 GB de RAM.</small></div></div>
      <button className="primary-button" disabled={!files.length || !rights || busy || !systemReady} onClick={submit}>
        {busy ? <Loader2 className="spin" size={19} /> : <Scissors size={19} />} {busy ? 'Agregando a la cola…' : 'Crear clips'} <ChevronRight size={18} />
      </button>
    </section>
  </div>
}

function JobCard({ job, onRefresh }) {
  const [showLogs, setShowLogs] = useState(false)
  const result = job.result || {}
  const clips = result.clips || []
  const logs = job.logs || []
  const lastLog = logs.slice(-1)[0]
  const failure = job.error || [...logs].reverse().find((line) =>
    !/^Process failed with exit code/i.test(line) &&
    /(error|exception|traceback|fatal|falló|failed|no metadata|no clips)/i.test(line)
  ) || lastLog
  return <article className={`job-card ${job.status}`}>
    <div className="job-top">
      <div className="job-file"><div className="file-icon"><Film size={18} /></div><div><strong>{job.name}</strong><small>{new Date(job.createdAt).toLocaleString('es-CL')}</small></div></div>
      <span className="status"><i />{statusLabel[job.status] || job.status}</span>
    </div>
    {job.status !== 'completed' && job.status !== 'failed' && <div className="processing-line"><div className="indeterminate" /><p>{lastLog || 'Preparando motor local…'}</p></div>}
    {job.status === 'failed' && <div className="error-line"><AlertTriangle size={17} /><span><strong>No se completó este video</strong>{failure || 'El proceso no terminó.'}</span></div>}
    {showLogs && <pre className="job-log">{logs.join('\n') || 'No hay líneas registradas para este intento.'}</pre>}
    {clips.length > 0 && <div className="clip-grid">
      {clips.map((clip, index) => <div className="clip-card" key={`${clip.video_url}-${index}`}>
        <video src={clip.video_url} controls preload="metadata" />
        <div><strong>{clip.video_title_for_youtube_short || `Clip ${index + 1}`}</strong><small>{Math.round((clip.end || 0) - (clip.start || 0))}s · score {clip.predicted_score || '—'}</small></div>
        <a className="icon-button" href={clip.video_url} download><Download size={16} /></a>
      </div>)}
    </div>}
    <div className="job-actions">
      {(job.status === 'processing' || job.status === 'queued') && <button className="ghost-button" onClick={() => onRefresh(job.id)}><RefreshCw size={15} /> Actualizar</button>}
      {job.status === 'failed' && <button className="ghost-button" onClick={() => setShowLogs((value) => !value)}><Eye size={15} /> {showLogs ? 'Ocultar registro' : 'Ver registro'}</button>}
      {job.status === 'failed' && <a className="ghost-button red" href={`/api/local/diagnostics/${job.id}`} download><Download size={15} /> Descargar diagnóstico</a>}
      {clips.length > 0 && <a className="ghost-button red" href={`/api/jobs/${job.id}/download-all`}><Download size={15} /> Descargar lote ZIP</a>}
    </div>
  </article>
}

function Queue({ jobs, refreshJob }) {
  const active = jobs.filter((job) => ['queued', 'processing'].includes(job.status)).length
  const ids = jobs.filter((job) => job.status === 'completed').map((job) => job.id)
  return <div className="stack-page">
    <div className="metrics">
      <div><Clock3 /><span>Activos</span><strong>{active}</strong></div><div><CheckCircle2 /><span>Terminados</span><strong>{jobs.filter((j) => j.status === 'completed').length}</strong></div><div><Film /><span>Clips listos</span><strong>{jobs.reduce((n, j) => n + (j.result?.clips?.length || 0), 0)}</strong></div>
    </div>
    <div className="list-heading"><div><h2>Cola actual</h2><p>La aplicación serializa trabajos para mantener estable tu notebook.</p></div>{ids.length > 1 && <a className="ghost-button red" href={`/api/local/batch-export?jobs=${ids.join(',')}`}><Download size={16} /> Exportar todo</a>}</div>
    {jobs.length ? jobs.map((job) => <JobCard key={job.id} job={job} onRefresh={refreshJob} />) : <Empty icon={Layers3} title="La cola está vacía" text="Agrega uno o varios videos desde Crear clips." />}
  </div>
}

function Empty({ icon: Icon, title, text }) {
  return <div className="empty"><div><Icon size={28} /></div><h3>{title}</h3><p>{text}</p></div>
}

function HistoryPage({ projects, reload }) {
  return <div className="stack-page">
    <div className="list-heading"><div><h2>Proyectos en este equipo</h2><p>Se reconstruye desde los metadatos y clips guardados en disco.</p></div><div className="inline-actions"><button className="ghost-button" onClick={reload}><RefreshCw size={16} /> Actualizar</button><button className="ghost-button" onClick={() => request('/api/local/open-output', { method: 'POST' })}><FolderOpen size={16} /> Abrir carpeta</button></div></div>
    <div className="history-list">
      {projects.map((project) => <article key={project.id} className="history-row">
        <div className="history-thumb"><MonitorPlay size={24} /><span>{project.clipCount || project.clips?.length || 0}</span></div>
        <div className="history-main"><strong>{project.title}</strong><small>{new Date(project.createdAt).toLocaleString('es-CL')} · {project.format || 'vertical'}</small></div>
        <div className="history-score"><span>ESTADO</span><strong>{statusLabel[project.status] || project.status}</strong></div>
        {project.clips?.length > 0 && <a className="ghost-button red" href={`/api/jobs/${project.id}/download-all`}><Download size={15} /> ZIP</a>}
      </article>)}
      {!projects.length && <Empty icon={History} title="Todavía no hay proyectos" text="Los trabajos terminados aparecerán aquí incluso después de reiniciar." />}
    </div>
  </div>
}

function ProfileEditor({ source, onClose, onSave }) {
  const [draft, setDraft] = useState(() => ({ ...source, name: source.builtin ? `${source.name} PERSONAL` : source.name, caption_style: { ...source.caption_style }, builtin: false }))
  const update = (key, value) => setDraft((current) => ({ ...current, [key]: value }))
  return <div className="modal-backdrop"><div className="modal">
    <div className="modal-title"><div><span>PERFIL LOCAL</span><h2>{source.builtin ? 'Duplicar perfil' : 'Editar perfil'}</h2></div><button className="icon-button" onClick={onClose}><X /></button></div>
    <label>Nombre<input value={draft.name} onChange={(e) => update('name', e.target.value)} /></label>
    <div className="form-pair"><label>Clips objetivo<input type="number" min="1" max="15" value={draft.target_clips} onChange={(e) => update('target_clips', +e.target.value)} /></label><label>Encoder<select value={draft.encoder} onChange={(e) => update('encoder', e.target.value)}><option value="qsv">Intel Quick Sync</option><option value="auto">Automático</option><option value="x264">CPU x264</option></select></label></div>
    <div className="form-pair"><label>Duración mínima<input type="number" value={draft.min_seconds} onChange={(e) => update('min_seconds', +e.target.value)} /></label><label>Duración máxima<input type="number" value={draft.max_seconds} onChange={(e) => update('max_seconds', +e.target.value)} /></label></div>
    <div className="form-pair"><label>Color activo<input type="color" value={draft.caption_style.highlight_color} onChange={(e) => update('caption_style', { ...draft.caption_style, highlight_color: e.target.value })} /></label><label>Tamaño subtítulo<input type="number" min="18" max="96" value={draft.caption_style.font_size} onChange={(e) => update('caption_style', { ...draft.caption_style, font_size: +e.target.value })} /></label></div>
    <label>Layouts automáticos<div className="check-grid">{[['split', 'Dos personas'], ['screencast', 'Pantalla'], ['speaker_cut', 'Corte hablante'], ['punch_in', 'Punch-in']].map(([id, text]) => <button key={id} className={draft.layouts.includes(id) ? 'on' : ''} onClick={() => update('layouts', draft.layouts.includes(id) ? draft.layouts.filter((x) => x !== id) : [...draft.layouts, id])}><span><Check size={13} /></span>{text}</button>)}</div></label>
    <div className="modal-actions"><button className="ghost-button" onClick={onClose}>Cancelar</button><button className="primary-button compact" onClick={() => onSave(draft)}><Check size={16} /> Guardar perfil</button></div>
  </div></div>
}

function ProfilesPage({ profiles, reload }) {
  const [editing, setEditing] = useState(null)
  const save = async (draft) => {
    if (editing.builtin) await request('/api/local/profiles', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft) })
    else await request(`/api/local/profiles/${editing.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft) })
    setEditing(null); reload()
  }
  return <div className="stack-page">
    <div className="list-heading"><div><h2>Recetas de edición</h2><p>Clips, layout, subtítulos, Whisper y encoder viajan juntos.</p></div></div>
    <div className="profile-cards">{profiles.map((profile) => <article key={profile.id} className="profile-card" style={{ '--accent': profile.accent }}>
      <div className="profile-card-top"><span className="profile-badge">{profile.builtin ? 'BASE' : 'PERSONAL'}</span><span className="large-swatch" /></div>
      <h3>{profile.name}</h3><p>{profile.description}</p>
      <div className="profile-stats"><span><strong>{profile.target_clips}</strong> clips</span><span><strong>{profile.min_seconds}–{profile.max_seconds}s</strong> duración</span><span><strong>{profile.encoder.toUpperCase()}</strong> encode</span></div>
      <div className="caption-preview" style={{ '--highlight': profile.caption_style.highlight_color }}>ESTO CAMBIA <em>TODO</em></div>
      <button className="ghost-button full" onClick={() => setEditing(profile)}>{profile.builtin ? <Copy size={15} /> : <Settings2 size={15} />}{profile.builtin ? 'Duplicar y personalizar' : 'Editar perfil'}</button>
    </article>)}</div>
    {editing && <ProfileEditor source={editing} onClose={() => setEditing(null)} onSave={save} />}
  </div>
}

function SystemPage({ system, reload }) {
  const [setup, setSetup] = useState(null)
  const startPull = async () => setSetup(await request('/api/local/setup/all', { method: 'POST' }))
  useEffect(() => {
    if (!setup || ['completed', 'failed'].includes(setup.status)) return
    const timer = setTimeout(() => request(`/api/local/setup/${setup.id}`).then(setSetup), 1200)
    return () => clearTimeout(timer)
  }, [setup])
  const entries = system ? Object.entries(system.components || {}) : []
  return <div className="stack-page">
    <div className="system-hero"><div><span className={`hero-icon ${system?.ready ? 'ready' : ''}`}><Cpu size={28} /></span><div><span>DIAGNÓSTICO LOCAL</span><h2>{system?.ready ? 'Listo para cortar sin Internet' : 'Completa la preparación inicial'}</h2><p>{system?.memoryProfile} · {system?.freeDiskGb ?? '—'} GB libres</p></div></div><div className="inline-actions">{!system?.ready && <button className="ghost-button red" disabled={setup && !['completed', 'failed'].includes(setup.status)} onClick={startPull}><Download size={16} /> Preparar modelos</button>}<button className="ghost-button" onClick={reload}><RefreshCw size={16} /> Volver a comprobar</button></div></div>
    <div className="component-grid">{entries.map(([key, item]) => <article key={key} className={item.ok && (key !== 'ollama' || item.modelInstalled) ? 'ok' : ''}>
      <div><span>{item.ok && (key !== 'ollama' || item.modelInstalled) ? <CheckCircle2 /> : <AlertTriangle />}</span><div><strong>{({ ffmpeg: 'FFmpeg', ffprobe: 'FFprobe', quickSync: 'Intel Quick Sync', ollama: 'Ollama + Qwen', fasterWhisper: 'Faster-Whisper', yolo: 'YOLO', mediaPipe: 'MediaPipe' })[key] || key}</strong><small>{item.detail}</small></div></div>
      {key === 'ollama' && !item.modelInstalled && item.ok && <button className="mini-button" onClick={startPull}><Download size={14} /> Preparar todo</button>}
    </article>)}</div>
    {setup && <section className="panel setup-log"><div className="section-heading"><div><span>{setup.status === 'completed' ? '✓' : '…'}</span><h2>Preparando Qwen, YOLO y Whisper</h2></div><small>{setup.status}</small></div><pre>{(setup.logs || []).slice(-12).join('\n') || 'Iniciando descarga…'}</pre>{setup.status === 'completed' && <button className="ghost-button red" onClick={() => { setSetup(null); reload() }}>Comprobar motor</button>}</section>}
    <section className="offline-note"><WifiOff size={21} /><div><strong>Qué significa “full offline”</strong><p>Después de instalar Ollama y descargar una vez Qwen, Whisper y YOLO, el procesamiento no requiere Internet. Los modelos no vienen dentro del instalador para evitar un .exe de varios GB.</p></div></section>
  </div>
}

export default function App() {
  const [page, setPage] = useState('studio')
  const [profiles, setProfiles] = useState([])
  const [jobs, setJobs] = useState(savedJobs)
  const [projects, setProjects] = useState([])
  const [system, setSystem] = useState(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')

  const loadProfiles = useCallback(() => request('/api/local/profiles').then((data) => setProfiles(data.profiles || [])).catch((e) => setToast(e.message)), [])
  const loadHistory = useCallback(() => request('/api/local/history').then((data) => setProjects(data.projects || [])).catch((e) => setToast(e.message)), [])
  const loadSystem = useCallback(() => request('/api/local/system').then(setSystem).catch((e) => setToast(e.message)), [])

  useEffect(() => { loadProfiles(); loadHistory(); loadSystem() }, [loadProfiles, loadHistory, loadSystem])
  useEffect(() => { localStorage.setItem('mapa-roto-jobs', JSON.stringify(jobs.slice(0, 40))) }, [jobs])

  const refreshJob = useCallback(async (id) => {
    try {
      const status = await request(`/api/status/${id}`)
      setJobs((all) => all.map((job) => job.id === id ? { ...job, ...status } : job))
      if (['completed', 'failed'].includes(status.status)) loadHistory()
    } catch (error) {
      setJobs((all) => all.map((job) => job.id === id ? { ...job, error: error.message } : job))
    }
  }, [loadHistory])

  useEffect(() => {
    const active = jobs.filter((job) => ['queued', 'processing'].includes(job.status))
    if (!active.length) return
    const timer = setInterval(() => active.forEach((job) => refreshJob(job.id)), 2200)
    return () => clearInterval(timer)
  }, [jobs, refreshJob])

  const submit = async (files, profile) => {
    setBusy(true)
    try {
      for (const file of files) {
        const form = new FormData()
        form.append('file', file); form.append('acknowledged', 'true')
        form.append('output_format', profile.output_format)
        form.append('layouts', (profile.layouts || []).join(','))
        form.append('target_clips', String(profile.target_clips))
        form.append('clip_min_seconds', String(profile.min_seconds))
        form.append('clip_max_seconds', String(profile.max_seconds))
        form.append('auto_hook', String(profile.auto_hook))
        form.append('auto_hook_style', profile.auto_hook_style || 'classic')
        form.append('captions', String(profile.captions))
        form.append('caption_style', JSON.stringify(profile.caption_style))
        form.append('encoder', profile.encoder || 'qsv')
        form.append('whisper_model', profile.whisper_model || 'small')
        form.append('whisper_language', profile.whisper_language || 'es')
        const created = await request('/api/process', { method: 'POST', body: form })
        setJobs((all) => [{ id: created.job_id, name: file.name, status: created.status, logs: [], result: null, createdAt: Date.now(), profile: profile.name }, ...all])
      }
      setPage('queue'); setToast(`${files.length} fuente${files.length > 1 ? 's' : ''} agregada${files.length > 1 ? 's' : ''} a la cola`)
    } catch (error) { setToast(error.message) } finally { setBusy(false) }
  }

  const activeCount = useMemo(() => jobs.filter((job) => ['queued', 'processing'].includes(job.status)).length, [jobs])
  return <div className="app-shell">
    <Sidebar page={page} setPage={setPage} queueCount={activeCount} />
    <main><Header page={page} system={system} /><div className="content">
      {page === 'studio' && <Studio profiles={profiles} onSubmit={submit} busy={busy} systemReady={Boolean(system?.ready)} onOpenSystem={() => setPage('system')} />}
      {page === 'queue' && <Queue jobs={jobs} refreshJob={refreshJob} />}
      {page === 'history' && <HistoryPage projects={projects} reload={loadHistory} />}
      {page === 'profiles' && <ProfilesPage profiles={profiles} reload={loadProfiles} />}
      {page === 'system' && <SystemPage system={system} reload={loadSystem} />}
    </div></main>
    {toast && <button className="toast" onClick={() => setToast('')}><CheckCircle2 size={17} />{toast}<X size={14} /></button>}
  </div>
}
