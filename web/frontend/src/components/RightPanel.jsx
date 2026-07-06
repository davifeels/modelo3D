import { useState } from 'react'
import { t } from '../i18n.js'
import { useStore } from '../store.js'
import { api } from '../api.js'
import PaintTools from './PaintTools.jsx'
import ExportPanel from './ExportPanel.jsx'

// Paleta compartilhada com o Viewer3D — indexada pelo idx da parte no backend
const PART_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16']
const AXIS_COLORS = { x: '#ef4444', y: '#22c55e', z: '#7c3aed' }
const axisLabel = (a) => t(`axis_${a}`)

const ArrowRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const ArrowLeftIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M11 7H3M7 3L3 7l4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const HelpIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M5.5 5.5a1.5 1.5 0 0 1 3 0c0 1-1.5 1.5-1.5 2.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    <circle cx="7" cy="10.5" r=".7" fill="currentColor"/>
  </svg>
)
const ScissorsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <circle cx="4" cy="4" r="2.2" stroke="currentColor" strokeWidth="1.4"/>
    <circle cx="4" cy="12" r="2.2" stroke="currentColor" strokeWidth="1.4"/>
    <path d="M6 5.5L12 10M6 10.5L12 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
)
const MagicIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <path d="M8 2l1.2 3.6L13 7l-3.8 1.4L8 12l-1.2-3.6L3 7l3.8-1.4L8 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
    <path d="M13 1v3M14.5 2.5H12M3 11v2M4 12H2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
)

// ── Painel de corte automático ────────────────────────────────────────────────
function AutoCutPanel() {
  const {
    cutSuggestions, activeCutPlane, modelBounds, sessionId, selectedPart,
    setActiveCutPlane, afterAutoCut, setLoading, setError,
  } = useStore()

  const axis = activeCutPlane?.axis || 'z'
  const axisIdx = { x: 0, y: 1, z: 2 }[axis]
  const boundsMin = modelBounds ? modelBounds.min[axisIdx] : 0
  const boundsMax = modelBounds ? modelBounds.max[axisIdx] : 100
  const span = boundsMax - boundsMin || 1

  const pos = activeCutPlane?.position ?? (boundsMin + boundsMax) / 2
  const pct = Math.round(((pos - boundsMin) / span) * 100)

  async function applyCut() {
    if (!activeCutPlane) return
    setLoading(true, t('applying_cut'), 40)
    try {
      const res = await api.cut(sessionId, selectedPart, activeCutPlane.axis, activeCutPlane.position)
      afterAutoCut(res.parts_meta, res.cut_origin, res.cut_normal, res.part_a_idx, res.part_b_idx)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Sugestões automáticas */}
      {cutSuggestions.length > 0 && (
        <div className="rp-section">
          <div className="rp-label">{t('suggested_cuts')}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {cutSuggestions.map((s, i) => {
              const isActive = activeCutPlane?.axis === s.axis &&
                Math.abs((activeCutPlane?.position ?? -999) - s.position) < 0.5
              return (
                <button
                  key={i}
                  onClick={() => setActiveCutPlane(s.axis, s.position)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 10px', borderRadius: 8,
                    border: `1.5px solid ${isActive ? AXIS_COLORS[s.axis] : 'var(--b2)'}`,
                    background: isActive ? `${AXIS_COLORS[s.axis]}22` : 'var(--e3)',
                    color: 'inherit', cursor: 'pointer', textAlign: 'left',
                    transition: 'all 0.15s',
                  }}
                >
                  <span style={{
                    width: 10, height: 10, borderRadius: 2, flexShrink: 0,
                    background: AXIS_COLORS[s.axis],
                  }} />
                  <span style={{ flex: 1, fontSize: 13 }}>
                    {axisLabel(s.axis)}
                  </span>
                  <span style={{ fontSize: 11, opacity: 0.5 }}>
                    {Math.round(s.score * 100)}%
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Ajuste fino da posição */}
      {activeCutPlane && (
        <div className="rp-section">
          <div className="rp-label">{t('fine_adjust')}</div>

          {/* Seletor de eixo */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
            {['x', 'y', 'z'].map(a => (
              <button key={a} onClick={() => {
                const mid = modelBounds
                  ? (modelBounds.min[{x:0,y:1,z:2}[a]] + modelBounds.max[{x:0,y:1,z:2}[a]]) / 2
                  : 0
                setActiveCutPlane(a, mid)
              }} style={{
                flex: 1, padding: '5px 0', borderRadius: 6,
                border: `1.5px solid ${axis === a ? AXIS_COLORS[a] : 'var(--b2)'}`,
                background: axis === a ? `${AXIS_COLORS[a]}22` : 'transparent',
                color: axis === a ? AXIS_COLORS[a] : 'inherit',
                cursor: 'pointer', fontWeight: axis === a ? 700 : 400,
                fontSize: 13,
              }}>{a.toUpperCase()}</button>
            ))}
          </div>

          <div className="slider-block">
            <div className="slider-head">
              <span>{t('position')}</span>
              <span className="slider-val">{pos.toFixed(1)} mm ({pct}%)</span>
            </div>
            <input
              className="styled-range"
              type="range"
              min={boundsMin}
              max={boundsMax}
              step={(boundsMax - boundsMin) / 200}
              value={pos}
              onChange={e => setActiveCutPlane(axis, Number(e.target.value))}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, opacity: 0.4, marginTop: 2 }}>
              <span>{boundsMin.toFixed(0)} mm</span>
              <span>{boundsMax.toFixed(0)} mm</span>
            </div>
          </div>
        </div>
      )}

      {/* Sem sugestões */}
      {cutSuggestions.length === 0 && (
        <div className="rp-section">
          <p className="rp-hint">{t('no_cut_found')}</p>
        </div>
      )}
    </>
  )
}

export default function RightPanel({ viewerRef }) {
  const {
    step, parts, selectedPart, completedNames,
    sessionId, cutOrigin, cutNormal, partAIdx, partBIdx,
    afterPreview, afterConfirm, afterSuggestCuts, activeCutPlane,
    setLoading, setError, cutAgain,
    viewMode, showWireframe, showJoints, jointPins, jointParams, paintedCount, lang,
    jointType, jointFit, setJointType, setJointFit,
  } = useStore()

  async function handleSuggestCuts() {
    setLoading(true, t('analyzing'), 30)
    try {
      const res = await api.suggestCuts(sessionId, selectedPart)
      afterSuggestCuts(res.suggestions, res.bounds)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handlePreviewJoints(typeOverride, fitOverride) {
    const jt = typeOverride ?? jointType
    const fit = fitOverride ?? jointFit
    setLoading(true, t('proc_joints'), 50)
    try {
      const res = await api.previewJoints(sessionId, partAIdx, partBIdx, cutOrigin, cutNormal, jt, fit)
      afterPreview(res.pins, {
        n_pins: res.n_pins, pin_diameter: res.pin_diameter, pin_depth: res.pin_depth,
        tolerance: res.tolerance, joint_type: res.joint_type, fit: res.fit,
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function changeJointType(jt) {
    if (jt === jointType) return
    setJointType(jt)
    // Já tem preview na tela → regenera com o novo tipo
    if (jointPins?.length) handlePreviewJoints(jt, undefined)
  }

  function changeJointFit(fit) {
    if (fit === jointFit) return
    setJointFit(fit)
    if (jointPins?.length) handlePreviewJoints(undefined, fit)
  }

  async function handleConfirm() {
    setLoading(true, t('proc_joints'), 60)
    try {
      const res = await api.confirm(sessionId, partAIdx, partBIdx, cutOrigin, cutNormal, jointType, jointFit)
      afterConfirm(res.parts_meta, res.warnings || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (step === 'idle') return null

  return (
    <div className="right-panel">
      {/* ── Cabeçalho do painel ────────────────────────────── */}
      <div className="rp-header">
        <span className="rp-title">
          {step === 'loaded'      ? t('rp_auto_cut')
          : step === 'cutting'    ? t('rp_adjust_cut')
          : step === 'painting'   ? t('rp_manual_sel')
          : step === 'previewing' ? t('rp_preview')
          : step === 'result'     ? t('rp_view_export')
          : t('rp_tools')}
        </span>
      </div>

      {/* ── Corpo ──────────────────────────────────────────── */}
      <div className="rp-body">

        {/* STEP: loaded */}
        {step === 'loaded' && (
          <div className="rp-section">
            <div style={{
              background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.2)',
              borderRadius: 10, padding: '14px 14px 16px', marginBottom: 12,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <MagicIcon />
                <span style={{ fontWeight: 600, fontSize: 14 }}>{t('smart_cut_title')}</span>
              </div>
              <p className="rp-hint" style={{ margin: 0, lineHeight: 1.6, fontSize: 12 }}>
                {t('smart_cut_desc')}
              </p>
            </div>
          </div>
        )}

        {/* STEP: cutting */}
        {step === 'cutting' && <AutoCutPanel />}

        {/* STEP: painting */}
        {step === 'painting' && (
          <PaintTools viewerRef={viewerRef} />
        )}

        {/* STEP: previewing */}
        {step === 'previewing' && (
          <>
            {/* Tipo de conector + assembly fit */}
            <div className="rp-section">
              <div className="rp-label">{t('joint_type_label')}</div>
              <div className="btn-row" style={{ marginBottom: 10 }}>
                {['pin', 'ball', 'dovetail'].map((jt) => (
                  <button
                    key={jt}
                    className={`fmt-btn ${jointType === jt ? 'active' : ''}`}
                    onClick={() => changeJointType(jt)}
                  >
                    {t('joint_' + jt)}
                  </button>
                ))}
              </div>
              <div className="rp-label">{t('fit_label')}</div>
              <div className="btn-row">
                {['flexivel', 'apertado'].map((f) => (
                  <button
                    key={f}
                    className={`fmt-btn ${jointFit === f ? 'active' : ''}`}
                    onClick={() => changeJointFit(f)}
                  >
                    {t('fit_' + f)}
                  </button>
                ))}
              </div>
              <p className="rp-hint" style={{ marginTop: 8, marginBottom: 0, fontSize: 11, lineHeight: 1.5 }}>
                {t('joint_hint_' + jointType)} {t('fit_hint_' + jointFit)}
              </p>
            </div>

            {!jointPins?.length && (
              <div className="rp-section">
                <p className="rp-hint" style={{ lineHeight: 1.6, marginBottom: 14 }}>
                  {t('preview_analyze')}
                </p>
                <button className="btn-generate-preview" onClick={() => handlePreviewJoints()}>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
                    <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  {t('btn_gen_preview')}
                </button>
              </div>
            )}

            {jointPins?.length > 0 && jointParams && (
              <>
                <div className="rp-section">
                  <div className="rp-label">{t('joint_params')}</div>
                  <div className="preview-stats">
                    <div className="pstat">
                      <span className="pstat-label">{t('total_pins')}</span>
                      <span className="pstat-value">{jointParams.n_pins}</span>
                    </div>
                    <div className="pstat">
                      <span className="pstat-label">{t('pin_diameter')}</span>
                      <span className="pstat-value">{jointParams.pin_diameter?.toFixed(2)} <small>mm</small></span>
                    </div>
                    <div className="pstat">
                      <span className="pstat-label">{t('pin_depth')}</span>
                      <span className="pstat-value">{jointParams.pin_depth?.toFixed(1)} <small>mm</small></span>
                    </div>
                    <div className="pstat">
                      <span className="pstat-label">{t('total_clearance')}</span>
                      <span className="pstat-value">{(jointParams.tolerance * 2)?.toFixed(2)} <small>mm</small></span>
                    </div>
                  </div>
                </div>
                <div className="rp-section">
                  <div className="rp-label">{t('legend')}</div>
                  <div className="preview-legend">
                    <div className="pleg-item">
                      <span className="pleg-dot" style={{ background: '#2563eb' }} />
                      <span>{t('parts_a')}</span>
                    </div>
                    <div className="pleg-item">
                      <span className="pleg-dot" style={{ background: '#dc2626' }} />
                      <span>{t('parts_b')}</span>
                    </div>
                  </div>
                </div>
                <div className="rp-section">
                  <p className="rp-hint" style={{ lineHeight: 1.5 }}>
                    {t('preview_check')}
                  </p>
                </div>
              </>
            )}
          </>
        )}

        {/* STEP: result */}
        {step === 'result' && (
          <>
            {/* Todas as partes cortadas — qualquer uma pode ser dividida de novo */}
            <div className="rp-section">
              <div className="rp-label" style={{ marginBottom: 8 }}>
                {t('parts_all')} ({parts.length})
              </div>
              <p className="rp-hint" style={{ marginBottom: 10, lineHeight: 1.5 }}>
                {t('cut_more_hint')}
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {parts.map((p) => {
                  const color = PART_COLORS[p.idx % PART_COLORS.length]
                  const done = completedNames.includes(p.name)
                  return (
                    <button
                      key={p.idx}
                      onClick={() => cutAgain(p.idx)}
                      title={t('cut_more')}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
                        border: '1.5px solid var(--b2)', background: 'var(--e3)',
                        color: 'inherit', textAlign: 'left', transition: 'all 0.15s',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = color; e.currentTarget.style.background = `${color}18` }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--b2)'; e.currentTarget.style.background = 'var(--e3)' }}
                    >
                      <span style={{ width: 10, height: 10, borderRadius: 3, background: color, flexShrink: 0 }} />
                      <span style={{ flex: 1, fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                      {done && (
                        <span style={{ fontSize: 10, color: '#22c55e', display: 'flex', alignItems: 'center', gap: 3, flexShrink: 0 }}>
                          <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                            <path d="M2 6l3 3 5-5" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                          {t('part_done_tag')}
                        </span>
                      )}
                      <span style={{ fontSize: 11, opacity: 0.45, flexShrink: 0 }}>{p.face_count?.toLocaleString()} {t('faces_suffix')}</span>
                      <ScissorsIcon />
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="rp-section">
              <div className="rp-label">{t('view_title')}</div>
              <div className="view-mode-cards">
                {[['side', 'view_side'], ['tabs', 'view_tabs'], ['same', 'view_same']].map(([vm, key]) => (
                  <button
                    key={vm}
                    className={`view-mode-card ${viewMode === vm ? 'active' : ''}`}
                    onClick={() => useStore.setState({ viewMode: vm })}
                  >{t(key)}</button>
                ))}
              </div>
            </div>
            <div className="rp-section">
              <div className="rp-label">{t('overlays')}</div>
              <div className="toggle-row">
                <span className="toggle-label">{t('view_joints')}</span>
                <button className={`toggle-switch ${showJoints ? 'on' : ''}`}
                  onClick={() => useStore.setState(s => ({ showJoints: !s.showJoints }))}
                ><span className="toggle-knob" /></button>
              </div>
              <div className="toggle-row">
                <span className="toggle-label">{t('view_wireframe')}</span>
                <button className={`toggle-switch ${showWireframe ? 'on' : ''}`}
                  onClick={() => useStore.setState(s => ({ showWireframe: !s.showWireframe }))}
                ><span className="toggle-knob" /></button>
              </div>
            </div>
            <ExportPanel />
          </>
        )}
      </div>

      {/* ── Rodapé com navegação ───────────────────────────── */}
      <div className="rp-footer">
        {step === 'loaded' && (
          <>
            <button className="btn-next-step" onClick={handleSuggestCuts}>
              <MagicIcon /> {t('btn_detect_cuts')}
            </button>
            <div className="rp-footer-actions">
              <button className="btn-back" style={{ fontSize: 12 }}
                onClick={() => useStore.setState({ step: 'painting', paintedFaces: [], paintedCount: 0 })}>
                {t('btn_manual_sel')}
              </button>
              <button className="btn-back" onClick={() => useStore.getState().reset()}>
                <ArrowLeftIcon /> {t('btn_import_other')}
              </button>
            </div>
          </>
        )}

        {step === 'cutting' && (
          <>
            <button className="btn-next-step" disabled={!activeCutPlane}
              onClick={async () => {
                if (!activeCutPlane) return
                setLoading(true, t('applying_cut'), 40)
                try {
                  const res = await api.cut(sessionId, selectedPart, activeCutPlane.axis, activeCutPlane.position)
                  useStore.getState().afterAutoCut(res.parts_meta, res.cut_origin, res.cut_normal, res.part_a_idx, res.part_b_idx)
                } catch (e) {
                  setError(e.message)
                } finally {
                  setLoading(false)
                }
              }}>
              <ScissorsIcon /> {t('btn_apply_cut')} <ArrowRightIcon />
            </button>
            <div className="rp-footer-actions">
              <button className="btn-back" onClick={() => useStore.setState({ step: 'loaded' })}>
                <ArrowLeftIcon /> {t('btn_back')}
              </button>
              <button className="btn-back" style={{ fontSize: 12 }}
                onClick={() => useStore.setState({ step: 'painting', paintedFaces: [], paintedCount: 0 })}>
                {t('btn_manual_sel')}
              </button>
            </div>
          </>
        )}

        {step === 'painting' && (
          <>
            <button className="btn-next-step" disabled={paintedCount === 0}
              onClick={async () => {
                if (paintedCount === 0) { useStore.getState().setError(t('warn_no_faces')); return }
                const painted = useStore.getState().paintedFaces
                useStore.getState().setLoading(true, t('proc_cutting'), 40)
                try {
                  const res = await api.cutFromPainted(sessionId, selectedPart, painted)
                  useStore.getState().afterPaintCut(res.parts_meta, res.cut_origin, res.cut_normal, res.part_a_idx, res.part_b_idx)
                } catch (e) {
                  useStore.getState().setError(e.message || t('err_paint'))
                } finally {
                  useStore.getState().setLoading(false)
                }
              }}>
              {t('btn_next_step')} <ArrowRightIcon />
            </button>
            <div className="rp-footer-actions">
              <button className="btn-back" onClick={() => useStore.setState({ step: 'loaded', paintedFaces: [], paintedCount: 0 })}>
                <ArrowLeftIcon /> {t('btn_back')}
              </button>
            </div>
          </>
        )}

        {step === 'previewing' && (
          <>
            <button className="btn-next-step" onClick={handleConfirm}>
              {t('preview_confirm')} <ArrowRightIcon />
            </button>
            <div className="rp-footer-actions">
              <button className="btn-back" onClick={() => useStore.setState({ step: 'cutting', jointPins: [] })}>
                <ArrowLeftIcon /> {t('btn_adjust_cut')}
              </button>
            </div>
          </>
        )}

        {step === 'result' && (
          <div className="rp-footer-actions">
            <button className="btn-back" onClick={() => useStore.getState().reset()}>
              <ArrowLeftIcon /> {t('btn_import_new')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
