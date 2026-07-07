import { useRef, useEffect, useState } from 'react'
import { useStore } from './store.js'
import { t, setLang, getLang } from './i18n.js'
import { api } from './api.js'
import StepIndicator from './components/StepIndicator.jsx'
import DropZone, { uploadModelFile } from './components/DropZone.jsx'
import SidePanel from './components/SidePanel.jsx'
import RightPanel from './components/RightPanel.jsx'
import Viewer3D from './components/Viewer3D.jsx'
import './styles/globals.css'

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"
        stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M12 9.5A5.5 5.5 0 0 1 6.5 4a5.5 5.5 0 1 0 5.5 5.5z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
    </svg>
  )
}

function OpenIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M1.5 4a1 1 0 0 1 1-1h3l1.2 1.5h4.8a1 1 0 0 1 1 1V10a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1V4z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    </svg>
  )
}

function UndoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2.5 5.5h6a3 3 0 0 1 0 6H5M2.5 5.5L5 3M2.5 5.5L5 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

// ── Status bar inferior: etapa atual, modelo carregado, mensagens ────────────
function StatusBar() {
  const { step, info, paintedCount, loading, progressMsg, error, lang } = useStore()
  const stepKey = {
    idle: 'status_idle', loaded: 'status_loaded', cutting: 'status_cutting',
    multimask: 'status_multimask', painting: 'status_painting',
    previewing: 'status_previewing', processing: 'status_processing',
    result: 'status_result',
  }[step] || 'status_idle'

  return (
    <footer className="status-bar">
      <span className="sb-dot" data-state={loading ? 'busy' : step === 'idle' ? 'idle' : 'ok'} />
      <span className="sb-step">{loading ? (progressMsg || t('status_processing')) : t(stepKey)}</span>
      {info?.name && (
        <span className="sb-model" title={info.name}>
          {info.name} · {(info.faces || 0).toLocaleString()} {t('status_faces')}
        </span>
      )}
      {step === 'painting' && (
        <span className="sb-painted">{paintedCount.toLocaleString()} {t('status_painted')}</span>
      )}
      {error && <span className="sb-msg">{String(error).split('\n')[0]}</span>}
    </footer>
  )
}

function ProgressOverlay() {
  const { loading, progressMsg, progress } = useStore()
  if (!loading) return null
  return (
    <div className="progress-overlay">
      <div className="spinner"></div>
      <div className="progress-msg">{progressMsg || t('processing')}</div>
      <div className="progress-bar-wrap">
        <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  )
}

function Toast() {
  const { error, clearError } = useStore()
  useEffect(() => {
    if (!error) return
    const timer = setTimeout(clearError, 5000)
    return () => clearTimeout(timer)
  }, [error])
  if (!error) return null
  return (
    <div className="toast" onClick={clearError}>{error}</div>
  )
}

function PreviewBadge() {
  const step = useStore(s => s.step)
  const lang = useStore(s => s.lang)
  if (step !== 'previewing') return null
  return (
    <div className="preview-badge">
      <span style={{ color: '#60a5fa' }}>{t('parts_a')}</span>
      <span style={{ color: '#444466' }}>|</span>
      <span style={{ color: '#f87171' }}>{t('parts_b')}</span>
    </div>
  )
}

function ViewerArea({ viewerRef }) {
  const { step, viewMode, activeTab, lang } = useStore()
  const showWireframe = useStore(s => s.showWireframe)

  if (step === 'idle') return <DropZone />

  if (step === 'result' && viewMode === 'side') {
    return (
      <div className="split-viewer">
        <div className="split-viewer-pane">
          <div className="pane-label" style={{ color: '#2563eb' }}>{t('parts_a')}</div>
          <Viewer3D ref={viewerRef} paneIdx={0} />
        </div>
        <div className="split-viewer-pane">
          <div className="pane-label" style={{ color: '#dc2626' }}>{t('parts_b')}</div>
          <Viewer3D ref={viewerRef} paneIdx={1} />
        </div>
      </div>
    )
  }

  if (step === 'result' && viewMode === 'tabs') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className="tabs-bar">
          <button
            className={`tab-btn ${activeTab === 0 ? 'active' : ''}`}
            onClick={() => useStore.setState({ activeTab: 0 })}
          >
            {t('parts_a')}
          </button>
          <button
            className={`tab-btn ${activeTab === 1 ? 'active' : ''}`}
            onClick={() => useStore.setState({ activeTab: 1 })}
          >
            {t('parts_b')}
          </button>
        </div>
        <div style={{ flex: 1, position: 'relative' }}>
          <Viewer3D ref={viewerRef} activeTab={activeTab} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <PreviewBadge />
      <Viewer3D ref={viewerRef} />

      <div className="viewer-toolbar" onPointerDown={e => e.stopPropagation()} onClick={e => e.stopPropagation()}>
        <button className="btn-icon" title={t('tooltip_fit')} onClick={e => { e.stopPropagation(); viewerRef.current?.fitView() }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 5V2h3M11 2h3v3M2 11v3h3M11 14h3v-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <rect x="5" y="5" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.2"/>
          </svg>
        </button>
        <button
          className={`btn-icon ${showWireframe ? 'active' : ''}`}
          title={t('tooltip_wireframe')}
          onClick={e => { e.stopPropagation(); useStore.setState(s => ({ showWireframe: !s.showWireframe })) }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2L14 6v4L8 14L2 10V6L8 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
            <path d="M2 6l6 4 6-4M8 2v12" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" opacity=".5"/>
          </svg>
        </button>
      </div>
    </div>
  )
}

function RestoreModal() {
  const { restorePrompt, restoreSession, dismissRestore } = useStore()
  if (!restorePrompt) return null

  const { info } = restorePrompt
  const fileName = info?.name || ''
  const faces = info?.faces ? info.faces.toLocaleString() : ''

  return (
    <div className="restore-overlay">
      <div className="restore-modal">
        {/* Ícone com anel animado */}
        <div className="restore-icon-wrap">
          <div className="restore-icon-ring" />
          <div className="restore-icon-circle">
            <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
              <path d="M7 13a6 6 0 1 1 6 6" stroke="var(--p4)" strokeWidth="2" strokeLinecap="round"/>
              <path d="M7 17v-4h4" stroke="var(--p4)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        </div>

        {/* Texto */}
        <div className="restore-text">
          <h3 className="restore-title">{t('restore_title')}</h3>
          <p className="restore-msg">{t('restore_msg')}</p>
        </div>

        {/* Card do arquivo */}
        {fileName && (
          <div className="restore-file-card">
            <div className="rfc-icon">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 2h7l3 3v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" stroke="var(--p4)" strokeWidth="1.3"/>
                <path d="M10 2v4h4" stroke="var(--p4)" strokeWidth="1.3" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="rfc-info">
              <span className="rfc-name">{fileName}</span>
              {faces && <span className="rfc-meta">{faces} {t('faces_suffix')}</span>}
            </div>
          </div>
        )}

        {/* Ações */}
        <div className="restore-actions">
          <button className="restore-btn-primary" onClick={() => restoreSession(restorePrompt)}>
            {t('restore_yes')}
          </button>
          <button className="restore-btn-secondary" onClick={dismissRestore}>
            {t('restore_no')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const viewerRef = useRef()
  const fileInputRef = useRef()
  const { lang, setLang: storeLang, theme, setTheme, setRestorePrompt, step } = useStore()
  const paintedCount = useStore(s => s.paintedCount)

  function handleOpenFile(e) {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    if (useStore.getState().sessionId) useStore.getState().reset()
    uploadModelFile(file)
  }

  function handleUndo() {
    viewerRef.current?.undoPaint?.()
  }

  // Apply theme attribute
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // Check for saved session on load
  useEffect(() => {
    const saved = localStorage.getItem('zs_session')
    if (!saved) return
    let parsed
    try { parsed = JSON.parse(saved) } catch { return }
    if (!parsed?.sessionId) return

    api.checkSession(parsed.sessionId)
      .then(data => {
        setRestorePrompt({
          sessionId: data.session_id,
          info: data.info,
          parts: data.parts,
          // O backend não rastreia step nem pintura — vêm do localStorage,
          // senão a restauração perde as faces pintadas (bug corrigido).
          step: parsed.step || data.step,
          paintedFaces: parsed.paintedFaces || [],
          selectedPart: parsed.selectedPart ?? 0,
        })
      })
      .catch(() => {
        localStorage.removeItem('zs_session')
      })
  }, [])

  function toggleLang() {
    const nl = lang === 'pt' ? 'en' : 'pt'
    setLang(nl)
    storeLang(nl)
  }

  function toggleTheme() {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <div id="root" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <header className="app-header">
        <div className="header-logo">
          <span className="logo">ZefiroSplit</span>
          <span className="logo-sub">3D Mesh Splitter</span>
        </div>
        <StepIndicator />
        <div className="header-actions">
          <button className="btn-header" onClick={() => fileInputRef.current?.click()} title={t('toolbar_open')}>
            <OpenIcon /> <span>{t('toolbar_open')}</span>
          </button>
          <button
            className="btn-header"
            onClick={handleUndo}
            disabled={step !== 'painting' || paintedCount === 0}
            title={t('toolbar_undo')}
          >
            <UndoIcon /> <span>{t('toolbar_undo')}</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".stl,.obj,.STL,.OBJ"
            style={{ display: 'none' }}
            onChange={handleOpenFile}
          />
          <button className="theme-toggle" onClick={toggleTheme} title={theme === 'dark' ? t('theme_light') : t('theme_dark')}>
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
          <button className="lang-select" onClick={toggleLang}>
            {lang === 'pt' ? 'EN' : 'PT'}
          </button>
        </div>
      </header>

      {/* Body — 3 columns (painéis só aparecem quando há modelo carregado) */}
      <div className="app-body">
        {step !== 'idle' && <SidePanel viewerRef={viewerRef} />}
        <div className="viewer-area">
          <ViewerArea viewerRef={viewerRef} />
        </div>
        {step !== 'idle' && <RightPanel viewerRef={viewerRef} />}
      </div>

      <StatusBar />

      <ProgressOverlay />
      <Toast />
      <RestoreModal />
    </div>
  )
}
