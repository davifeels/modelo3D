import { t, tf } from '../i18n.js'
import { renderABText } from './SidePanel.jsx'
import { useStore } from '../store.js'
import { api } from '../api.js'

const BrushIcon = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
    <path d="M13 3l2 2-7 7c-1 0-2 1-2 2s-1 2-2 2h-1v-1c0-1 1-1 2-2s2-1 2-2l6-8z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
    <circle cx="4" cy="16" r="1.2" fill="currentColor" opacity=".5"/>
  </svg>
)

const FillIcon = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
    <path d="M10 3l7 7H3l7-7z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
    <path d="M4 14h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity=".5"/>
    <circle cx="15" cy="14" r="3" stroke="currentColor" strokeWidth="1.4"/>
    <path d="M15 12v4M13 14h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".6"/>
  </svg>
)

const UndoIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 5h6a4 4 0 1 1 0 8H6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M2 5l3-3M2 5l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const RedoIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M12 5H6a4 4 0 1 0 0 8h2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 5l-3-3M12 5l-3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const TrashIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2.5 4h9M5.5 4V2.5h3V4M3.5 4l.5 7.5h6L11 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const InfoIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M7 6.5v4M7 4.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
)

const EraserIcon = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
    <path d="M14 4L4 14l3 3 10-10-3-3z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
    <path d="M4 14l3 3H3l-1-1v-1l2-1z" fill="currentColor" opacity=".3"/>
    <path d="M8 17h9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
)

const FillGapsIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <rect x="1.5" y="1.5" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M4 7h6M7 4v6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity=".5"/>
    <circle cx="7" cy="7" r="1.5" fill="currentColor"/>
  </svg>
)

export default function PaintTools({ viewerRef }) {
  const {
    paintMode, clearPaintedFaces, brushSize, fillAngle, fillRadius, paintedCount,
    sessionId, selectedPart, afterPaintCut, setLoading, setError, lang,
  } = useStore()


  function handleClear() {
    clearPaintedFaces()
    viewerRef?.current?.clearPaint()
  }

  function handleUndo() {
    viewerRef?.current?.undoPaint()
  }

  function handleFillGaps() {
    viewerRef?.current?.fillPaintGaps()
  }

  async function handlePreview() {
    if (paintedCount === 0) { setError(t('warn_no_faces')); return }
    const painted = useStore.getState().paintedFaces
    setLoading(true, t('proc_cutting'), 40)
    try {
      const res = await api.cutFromPainted(sessionId, selectedPart, painted)
      afterPaintCut(res.parts_meta, res.cut_origin, res.cut_normal, res.part_a_idx, res.part_b_idx)
    } catch (e) {
      setError(e.message || t('err_paint'))
    } finally {
      setLoading(false)
    }
  }

  const total = useStore.getState().info?.faces || 0
  const pct = total > 0 ? ((paintedCount / total) * 100).toFixed(0) : 0

  return (
    <>
      {/* Modo de seleção */}
      <div className="rp-section">
        <div className="rp-label">{t('sel_mode')}</div>
        <div className="paint-mode-cards">
          <button
            className={`paint-mode-card ${paintMode === 'brush' ? 'active' : ''}`}
            onClick={() => useStore.setState({ paintMode: 'brush' })}
          >
            <div className="pmc-icon"><BrushIcon size={24} /></div>
            <div className="pmc-name">{t('paint_brush')}</div>
            <div className="pmc-sub">{t('paint_brush_sub')}</div>
          </button>
          <button
            className={`paint-mode-card ${paintMode === 'fill' ? 'active' : ''}`}
            onClick={() => useStore.setState({ paintMode: 'fill' })}
          >
            <div className="pmc-icon"><FillIcon size={24} /></div>
            <div className="pmc-name">{t('paint_fill')}</div>
            <div className="pmc-sub">{t('paint_fill_sub')}</div>
          </button>
          <button
            className={`paint-mode-card ${paintMode === 'eraser' ? 'active' : ''}`}
            onClick={() => useStore.setState({ paintMode: 'eraser' })}
            style={paintMode === 'eraser' ? { borderColor: '#f97316', background: 'rgba(249,115,22,0.12)' } : {}}
          >
            <div className="pmc-icon"><EraserIcon size={24} /></div>
            <div className="pmc-name">{t('paint_eraser')}</div>
            <div className="pmc-sub">{t('paint_eraser_sub')}</div>
          </button>
        </div>
      </div>

      {/* Configurações — muda conforme o modo */}
      <div className="rp-section">
        <div className="rp-label">
          {paintMode === 'fill' ? t('fill_sensitivity') : paintMode === 'eraser' ? t('eraser_size') : t('brush_settings')}
        </div>

        {(paintMode === 'brush' || paintMode === 'eraser') && (
          <div className="slider-block">
            <div className="slider-head">
              <span>{t('size_label')}</span>
              <span className="slider-val">{brushSize} mm</span>
            </div>
            <input
              className="styled-range"
              type="range" min={1} max={80} value={brushSize}
              onChange={e => useStore.setState({ brushSize: Number(e.target.value) })}
            />
          </div>
        )}

        {paintMode === 'fill' && (
          <>
            <div className="slider-block">
              <div className="slider-head">
                <span>{t('stop_angle')}</span>
                <span className="slider-val">{fillAngle}°</span>
              </div>
              <input
                className="styled-range"
                type="range" min={1} max={45} step={1} value={fillAngle}
                onChange={e => useStore.setState({ fillAngle: Number(e.target.value) })}
              />
              <div style={{ display:'flex', justifyContent:'space-between', fontSize:10, color:'var(--t3)', marginTop:2 }}>
                <span>{t('angle_scale_lo')}</span>
                <span>{t('angle_scale_hi')}</span>
              </div>
            </div>
            <p className="rp-hint" style={{ fontSize: 11, marginTop: 4, lineHeight: 1.5, color: 'var(--t2)' }}>
              {fillAngle <= 3
                ? t('angle_hint_1')
                : fillAngle <= 7
                ? t('angle_hint_2')
                : fillAngle <= 15
                ? t('angle_hint_3')
                : fillAngle <= 30
                ? t('angle_hint_4')
                : t('angle_hint_5')}
            </p>
            <div className="slider-block" style={{ marginTop: 10 }}>
              <div className="slider-head">
                <span>{t('max_radius')}</span>
                <span className="slider-val">{fillRadius === 0 ? t('unlimited') : `${fillRadius} mm`}</span>
              </div>
              <input
                className="styled-range"
                type="range" min={0} max={300} step={10} value={fillRadius}
                onChange={e => useStore.setState({ fillRadius: Number(e.target.value) })}
              />
              <div style={{ display:'flex', justifyContent:'space-between', fontSize:10, color:'var(--t3)', marginTop:2 }}>
                <span>{t('no_limit')}</span>
                <span>300 mm</span>
              </div>
              <p className="rp-hint" style={{ fontSize: 11, marginTop: 4, lineHeight: 1.5, color: 'var(--t2)' }}>
                {fillRadius === 0
                  ? t('radius_hint_0')
                  : fillRadius >= 150
                    ? tf('radius_hint_hi', { r: fillRadius })
                    : tf('radius_hint_lo', { r: fillRadius })}
              </p>
            </div>
          </>
        )}
      </div>

      {/* Ações */}
      <div className="rp-section">
        <div className="btn-row" style={{ marginBottom: 6 }}>
          <button className="btn-action" onClick={handleUndo} disabled={paintedCount === 0}>
            <UndoIcon /> {t('paint_undo')}
          </button>
          <button className="btn-clear-all" style={{ flex: 1 }} onClick={handleClear} disabled={paintedCount === 0}>
            <TrashIcon /> {t('paint_clear')}
          </button>
        </div>
        <button
          className="btn-action"
          style={{ width: '100%', justifyContent: 'center', gap: 6, background: 'var(--success-dim)', color: 'var(--success)', border: '1px solid var(--success)', opacity: paintedCount === 0 ? 0.4 : 1 }}
          onClick={handleFillGaps}
          disabled={paintedCount === 0}
          title={t('fill_gaps_tip')}
        >
          <FillGapsIcon /> {t('fill_gaps')}
        </button>
        <p style={{ fontSize: 10, color: 'var(--t3)', textAlign: 'center', marginTop: 4 }}>
          {t('undo_click_hint')}
        </p>
      </div>

      {/* Como funciona */}
      <div className="rp-section">
        <div className="how-it-works">
          <div className="hiw-title"><InfoIcon /> {t('how_works')}</div>
          <p className="hiw-text">
            {renderABText(t('hiw_paint_html'))}
          </p>
          <p className="hiw-text" style={{ marginTop: 6 }}>
            {t('hiw_fill')}
          </p>
          <p className="hiw-text" style={{ marginTop: 4 }}>
            {t('hiw_brush')}
          </p>
          <p className="hiw-text" style={{ marginTop: 6, color: 'var(--t2)' }}>
            {t('hiw_undo')}
          </p>
        </div>
      </div>

      {/* Faces pintadas */}
      <div className="rp-section" style={{ paddingTop: 8, paddingBottom: 8 }}>
        <div className="rp-stat-row">
          <span>{t('paint_faces')}</span>
          <span style={{ fontWeight: 700, color: paintedCount > 0 ? 'var(--p4)' : 'var(--t3)' }}>
            {paintedCount.toLocaleString()} ({pct}%)
          </span>
        </div>
      </div>
    </>
  )
}
