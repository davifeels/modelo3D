import { t } from '../i18n.js'
import { useStore } from '../store.js'
import InfoPanel from './InfoPanel.jsx'

const IconReset = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 7a5 5 0 1 0 1.5-3.5L2 2v3.5h3.5L4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IconXray = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <rect x="1.5" y="3" width="11" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <circle cx="7" cy="7" r="2" stroke="currentColor" strokeWidth="1" opacity=".5"/>
    <path d="M4 7h1.2M8.8 7H10" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity=".5"/>
  </svg>
)

const IconWireframe = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M7 1.5l5 3v5l-5 3-5-3v-5l5-3z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    <path d="M7 1.5v11.5M2 4.5l5 3 5-3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity=".4"/>
  </svg>
)
const IconGrid = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 2h10v10H2V2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    <path d="M2 7h10M7 2v10" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity=".5"/>
  </svg>
)
const IconCenter = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <rect x="4.5" y="4.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M7 1.5v2M7 10.5v2M1.5 7h2M10.5 7h2" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
  </svg>
)
const IconTrash = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2.5 4h9M5.5 4V2.5h3V4M6 6.5v4M8 6.5v4M3.5 4l.5 7.5h6L11 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IconInfo = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M7 6.5v4M7 4.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
)

// Renderiza texto com marcadores <a>/<b> como "Parte A"/"Parte B" coloridos
export function renderABText(s) {
  return s.split(/(<a>|<b>)/g).map((part, i) =>
    part === '<a>' ? <strong key={i} style={{ color: '#3b82f6' }}>{t('part_a_short')}</strong>
    : part === '<b>' ? <strong key={i} style={{ color: '#ef4444' }}>{t('part_b_short')}</strong>
    : part
  )
}

export default function SidePanel({ viewerRef }) {
  const { step, showWireframe, showGrid, showXray, lang } = useStore()

  function resetCamera() { viewerRef?.current?.resetCamera?.() }
  function fitView()     { viewerRef?.current?.fitView?.() }
  function clearPaint()  {
    useStore.getState().clearPaintedFaces()
    viewerRef?.current?.clearPaint?.()
  }

  return (
    <div className="side-panel">
      {/* Model info */}
      {step !== 'idle' && <InfoPanel />}

      {/* General tools */}
      {step !== 'idle' && (
        <div className="panel-section">
          <h3>{t('general_tools')}</h3>

          <button className="tool-row-btn" onClick={resetCamera}>
            <IconReset /> {t('reset_camera')}
          </button>

          <div className="tool-row-toggle">
            <span className="trt-left"><IconWireframe /> {t('show_wireframe')}</span>
            <button
              className={`toggle-switch ${showWireframe ? 'on' : ''}`}
              onClick={() => useStore.setState(s => ({ showWireframe: !s.showWireframe }))}
            >
              <span className="toggle-knob" />
            </button>
          </div>

          <div className="tool-row-toggle">
            <span className="trt-left"><IconGrid /> {t('show_grid')}</span>
            <button
              className={`toggle-switch ${showGrid ? 'on' : ''}`}
              onClick={() => useStore.setState(s => ({ showGrid: !s.showGrid }))}
            >
              <span className="toggle-knob" />
            </button>
          </div>

          <div className="tool-row-toggle">
            <span className="trt-left"><IconXray /> {t('show_xray')}</span>
            <button
              className={`toggle-switch ${showXray ? 'on' : ''}`}
              onClick={() => useStore.setState(s => ({ showXray: !s.showXray }))}
            >
              <span className="toggle-knob" />
            </button>
          </div>

          <button className="tool-row-btn" onClick={fitView}>
            <IconCenter /> {t('center_model')}
          </button>

          {(step === 'painting') && (
            <button className="tool-row-btn danger" onClick={clearPaint}>
              <IconTrash /> {t('clear_selection')}
            </button>
          )}
        </div>
      )}

      {/* Tips */}
      {(step === 'loaded' || step === 'painting') && (
        <div className="panel-section tips-section">
          <h3><IconInfo /> {t('tips_title')}</h3>
          <p className="tip-text">
            {renderABText(t('tip_paint_html'))}
          </p>
          <p className="tip-text" style={{ marginTop: 8 }}>
            {t('tip_undo')}
          </p>
        </div>
      )}
    </div>
  )
}
