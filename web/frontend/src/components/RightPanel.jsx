import { useState, useEffect } from 'react'
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
    selectedPinIdx, setSelectedPin, updatePin,
    maskLabels, maskRegionSizes, maskGranularity, selectedRegionId,
    afterSegmentMask, setSelectedRegion, exitMultiMask, afterMultiMaskCut,
    backToAssembly, afterRestoreOriginal,
  } = useStore()

  // Volta para a visão com TODAS as peças da sessão (fonte da verdade é o
  // backend — nada se perde mesmo se o frontend descartou peças ao editar
  // uma delas isoladamente via "cortar de novo").
  async function handleBackToAssembly() {
    setLoading(true, t('loading_model'), 50)
    try {
      const data = await api.checkSession(sessionId)
      backToAssembly(data.parts)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Descarta cortes/encaixes e volta ao mesh exatamente como veio do upload.
  async function handleRestoreOriginal() {
    if (!window.confirm(t('confirm_restore_original'))) return
    setLoading(true, t('loading_model'), 50)
    try {
      const res = await api.restoreOriginal(sessionId)
      afterRestoreOriginal(res.parts_meta)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

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

  // ── Modo Professional (§1): segmentação multi-peça ────────────────────────
  async function handleSegmentMask(granularity) {
    setLoading(true, t('proc_segmenting'), 40)
    try {
      const res = await api.segmentMask(sessionId, selectedPart, granularity)
      afterSegmentMask(res.labels, res.region_sizes, granularity)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMaskSplit() {
    if (selectedRegionId == null) return
    setLoading(true, t('proc_segmenting'), 40)
    try {
      const res = await api.maskSplit(sessionId, selectedPart, maskLabels, selectedRegionId)
      afterSegmentMask(res.labels, res.region_sizes, maskGranularity)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleApplyMask() {
    setLoading(true, t('proc_cutting'), 60)
    try {
      const res = await api.cutByMultiMask(sessionId, selectedPart, maskLabels)
      afterMultiMaskCut(res.parts_meta)
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
      // §2.2: envia o estado editado dos conectores — o backend gera
      // exatamente o que está no preview (incl. edições individuais)
      const pins = jointPins?.length ? jointPins.map(p => ({
        position: p.position,
        direction: p.direction,
        joint_type: p.joint_type,
        diameter: p.pin_radius * 2,
        depth: p.depth,
      })) : undefined
      const res = await api.confirm(sessionId, partAIdx, partBIdx, cutOrigin, cutNormal, jointType, jointFit, pins)
      afterConfirm(res.parts_meta, res.warnings || [])
      // O backend pode responder 200 com as peças intocadas (booleana falhou
      // silenciosamente) — sem isso o usuário só veria um aviso discreto no
      // rodapé e acharia que o encaixe foi criado.
      if (res.joint_applied === false) setError(t('err_joint_not_created'))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Base ortonormal (u,v) do plano ⊥ à normal — espelha _plane_basis do backend
  function planeBasis(n) {
    let u = [-n[1], n[0], 0]
    if (Math.hypot(...u) < 1e-6) u = [1, 0, 0]
    const d = u[0] * n[0] + u[1] * n[1] + u[2] * n[2]
    u = [u[0] - d * n[0], u[1] - d * n[1], u[2] - d * n[2]]
    const ul = Math.hypot(...u)
    u = u.map(c => c / ul)
    const v = [
      n[1] * u[2] - n[2] * u[1],
      n[2] * u[0] - n[0] * u[2],
      n[0] * u[1] - n[1] * u[0],
    ]
    return [u, v]
  }

  // §2.3: interfaces pendentes (cortes sem conector) para "Add all"
  const [pendingItf, setPendingItf] = useState(0)
  useEffect(() => {
    if (step !== 'result' || !sessionId) { setPendingItf(0); return }
    api.getInterfaces(sessionId)
      .then(r => setPendingItf(r.n_pending))
      .catch(() => setPendingItf(0))
  }, [step, sessionId, parts])

  function handleSkipJoints() {
    // Corte já está feito na sessão — só avança sem gerar conectores;
    // a interface fica registrada como pendente no backend.
    afterConfirm(parts, [])
  }

  async function handleConfirmAll() {
    setLoading(true, t('proc_joints'), 60)
    try {
      const res = await api.confirmAll(sessionId, jointType, jointFit)
      afterConfirm(res.parts_meta, res.warnings || [])
      setPendingItf(0)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function setPinAngles(idx, angleU, angleV) {
    const n = [...cutNormal]
    const nl = Math.hypot(...n)
    const nn = n.map(c => c / nl)
    const [u, v] = planeBasis(nn)
    const tu = Math.tan((angleU * Math.PI) / 180)
    const tv = Math.tan((angleV * Math.PI) / 180)
    let dir = [
      nn[0] + tu * u[0] + tv * v[0],
      nn[1] + tu * u[1] + tv * v[1],
      nn[2] + tu * u[2] + tv * v[2],
    ]
    const dl = Math.hypot(...dir)
    dir = dir.map(c => c / dl)
    updatePin(idx, { angleU, angleV, direction: dir })
  }

  if (step === 'idle') return null

  return (
    <div className="right-panel">
      {/* ── Cabeçalho do painel ────────────────────────────── */}
      <div className="rp-header">
        <span className="rp-title">
          {step === 'loaded'      ? t('rp_auto_cut')
          : step === 'cutting'    ? t('rp_adjust_cut')
          : step === 'multimask'  ? t('rp_multimask')
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

        {/* STEP: multimask (§1 — modo Professional) */}
        {step === 'multimask' && (() => {
          const regions = Object.entries(maskRegionSizes)
            .map(([id, n]) => [Number(id), n])
            .sort((a, b) => b[1] - a[1])
          return (
            <>
              <div className="rp-section">
                <div className="rp-label">{t('granularity_label')}</div>
                <div className="btn-row" style={{ marginBottom: 6 }}>
                  {['baixa', 'media', 'alta'].map((g) => (
                    <button key={g}
                      className={`fmt-btn ${maskGranularity === g ? 'active' : ''}`}
                      onClick={() => { if (g !== maskGranularity) handleSegmentMask(g) }}>
                      {t('gran_' + g)}
                    </button>
                  ))}
                </div>
                <p className="rp-hint" style={{ fontSize: 11, margin: 0, lineHeight: 1.5 }}>
                  {t('gran_hint')}
                </p>
              </div>

              <div className="rp-section">
                <div className="rp-label" style={{ marginBottom: 8 }}>
                  {t('regions_title')} ({regions.length})
                </div>
                {regions.length < 2 && (
                  <p className="rp-hint" style={{ lineHeight: 1.5, color: 'var(--warning, #f59e0b)' }}>
                    {t('mask_one_region')}
                  </p>
                )}
                {regions.length >= 2 && (
                  <p className="rp-hint" style={{ marginBottom: 10, lineHeight: 1.5 }}>
                    {t('mask_hint_select')}
                  </p>
                )}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {regions.map(([rid, nFaces]) => {
                    const color = PART_COLORS[rid % PART_COLORS.length]
                    const selected = rid === selectedRegionId
                    return (
                      <button key={rid}
                        onClick={() => setSelectedRegion(selected ? null : rid)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                          border: `1.5px solid ${selected ? color : 'var(--b2)'}`,
                          background: selected ? `${color}22` : 'var(--e3)',
                          color: 'inherit', textAlign: 'left', transition: 'all 0.15s',
                        }}>
                        <span style={{ width: 10, height: 10, borderRadius: 3, background: color, flexShrink: 0 }} />
                        <span style={{ flex: 1, fontSize: 13, fontWeight: selected ? 600 : 400 }}>
                          {t('region_label')} {rid + 1}
                        </span>
                        <span style={{ fontSize: 11, opacity: 0.45 }}>
                          {nFaces.toLocaleString()} {t('faces_suffix')}
                        </span>
                      </button>
                    )
                  })}
                </div>
                {selectedRegionId != null && (
                  <button className="btn-action"
                    style={{ width: '100%', justifyContent: 'center', gap: 6, marginTop: 10 }}
                    onClick={handleMaskSplit}>
                    <ScissorsIcon /> {t('btn_split_region')}
                  </button>
                )}
              </div>
            </>
          )
        })()}

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
                {/* §2.2: edição individual do conector selecionado */}
                {selectedPinIdx != null && jointPins[selectedPinIdx] ? (
                  <div className="rp-section" style={{
                    border: '1px solid var(--p2)', borderRadius: 10, padding: 12,
                  }}>
                    <div className="rp-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{t('pin_editor')} #{selectedPinIdx + 1}</span>
                      <button className="btn-ghost" style={{ fontSize: 11, padding: '2px 8px' }}
                              onClick={() => setSelectedPin(null)}>
                        {t('pin_editor_done')}
                      </button>
                    </div>

                    <div className="btn-row" style={{ margin: '8px 0 10px' }}>
                      {['pin', 'ball', 'dovetail'].map((jt) => (
                        <button key={jt}
                          className={`fmt-btn ${jointPins[selectedPinIdx].joint_type === jt ? 'active' : ''}`}
                          onClick={() => updatePin(selectedPinIdx, { joint_type: jt })}>
                          {t('joint_' + jt)}
                        </button>
                      ))}
                    </div>

                    <div className="slider-block">
                      <div className="slider-head">
                        <span>{t('edit_diameter')}</span>
                        <span className="slider-val">{(jointPins[selectedPinIdx].pin_radius * 2).toFixed(1)} mm</span>
                      </div>
                      <input className="styled-range" type="range"
                        min={2} max={Math.max(24, jointParams.pin_diameter * 2)} step={0.5}
                        value={jointPins[selectedPinIdx].pin_radius * 2}
                        onChange={e => {
                          const dia = Number(e.target.value)
                          updatePin(selectedPinIdx, {
                            pin_radius: dia / 2,
                            hole_radius: dia / 2 + (jointParams.tolerance ?? 1),
                          })
                        }} />
                    </div>

                    <div className="slider-block">
                      <div className="slider-head">
                        <span>{t('edit_depth')}</span>
                        <span className="slider-val">{jointPins[selectedPinIdx].depth.toFixed(1)} mm</span>
                      </div>
                      <input className="styled-range" type="range"
                        min={2} max={Math.max(30, jointParams.pin_depth * 2)} step={0.5}
                        value={jointPins[selectedPinIdx].depth}
                        onChange={e => updatePin(selectedPinIdx, { depth: Number(e.target.value) })} />
                    </div>

                    <div className="slider-block">
                      <div className="slider-head">
                        <span>{t('edit_angle_u')}</span>
                        <span className="slider-val">{(jointPins[selectedPinIdx].angleU ?? 0)}°</span>
                      </div>
                      <input className="styled-range" type="range" min={-30} max={30} step={1}
                        value={jointPins[selectedPinIdx].angleU ?? 0}
                        onChange={e => setPinAngles(selectedPinIdx, Number(e.target.value),
                                                    jointPins[selectedPinIdx].angleV ?? 0)} />
                    </div>

                    <div className="slider-block">
                      <div className="slider-head">
                        <span>{t('edit_angle_v')}</span>
                        <span className="slider-val">{(jointPins[selectedPinIdx].angleV ?? 0)}°</span>
                      </div>
                      <input className="styled-range" type="range" min={-30} max={30} step={1}
                        value={jointPins[selectedPinIdx].angleV ?? 0}
                        onChange={e => setPinAngles(selectedPinIdx, jointPins[selectedPinIdx].angleU ?? 0,
                                                    Number(e.target.value))} />
                    </div>
                  </div>
                ) : (
                  <div className="rp-section">
                    <p className="rp-hint" style={{ lineHeight: 1.5 }}>
                      {t('pin_editor_hint')}
                    </p>
                  </div>
                )}

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
            {/* §2.3: Add all connectors — interfaces cortadas sem conector */}
            {pendingItf > 0 && (
              <div className="rp-section" style={{
                border: '1px solid var(--p2)', borderRadius: 10, padding: 12,
              }}>
                <p className="rp-hint" style={{ margin: '0 0 10px', lineHeight: 1.5 }}>
                  {pendingItf} {t('pending_interfaces')}
                </p>
                <button className="btn-generate-preview" onClick={handleConfirmAll}>
                  {t('btn_add_all')}
                </button>
              </div>
            )}

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
            {/* §1: segmentação automática multi-peça */}
            <button className="btn-back" style={{ width: '100%', justifyContent: 'center', marginTop: 6 }}
              onClick={() => handleSegmentMask(maskGranularity || 'media')}>
              <ScissorsIcon /> {t('btn_pro_mode')}
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
            {completedNames.length > 0 && (
              <button className="btn-back" style={{ width: '100%', justifyContent: 'center', fontSize: 12, marginTop: 6 }}
                onClick={handleRestoreOriginal}>
                {t('btn_restore_original')}
              </button>
            )}
          </>
        )}

        {step === 'multimask' && (
          <>
            <button className="btn-next-step"
              disabled={!maskLabels || Object.keys(maskRegionSizes).length < 2}
              onClick={handleApplyMask}>
              <ScissorsIcon /> {t('btn_apply_mask')} ({Object.keys(maskRegionSizes).length} {t('pieces_suffix')}) <ArrowRightIcon />
            </button>
            <div className="rp-footer-actions">
              <button className="btn-back" onClick={exitMultiMask}>
                <ArrowLeftIcon /> {t('btn_back')}
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
            {completedNames.length > 0 && (
              <button className="btn-back" style={{ width: '100%', justifyContent: 'center', fontSize: 12, marginTop: 6 }}
                onClick={handleBackToAssembly}>
                <ArrowLeftIcon /> {t('btn_back_assembly')}
              </button>
            )}
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
            {completedNames.length > 0 && (
              <button className="btn-back" style={{ width: '100%', justifyContent: 'center', fontSize: 12, marginTop: 6 }}
                onClick={handleBackToAssembly}>
                <ArrowLeftIcon /> {t('btn_back_assembly')}
              </button>
            )}
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
              {/* §2.3: deixa a interface pendente p/ "Add all connectors" */}
              <button className="btn-back" style={{ fontSize: 12 }} onClick={handleSkipJoints}>
                {t('btn_skip_joints')} <ArrowRightIcon />
              </button>
            </div>
          </>
        )}

        {step === 'result' && (
          <div className="rp-footer-actions">
            <button className="btn-back" onClick={() => useStore.getState().reset()}>
              <ArrowLeftIcon /> {t('btn_import_new')}
            </button>
            <button className="btn-back" style={{ fontSize: 12 }} onClick={handleRestoreOriginal}>
              {t('btn_restore_original')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
