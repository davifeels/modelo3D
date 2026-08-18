import { create } from 'zustand'
import { getToken, setToken } from './api.js'

// step: idle | loaded | cutting | painting | previewing | processing | result
export const useStore = create((set, get) => ({
  // ── Auth / billing ──────────────────────────────────────────
  authToken: getToken(),      // JWT persistido no localStorage
  authUser: null,             // { id, email, name } — carregado no boot
  billingMe: null,            // resposta de GET /api/billing/me
  authChecked: false,         // boot terminou (evita flash da tela de login)

  setAuth: (token, user) => {
    setToken(token)
    set({ authToken: token, authUser: user })
  },

  setBillingMe: (billingMe) => set({ billingMe }),
  setAuthChecked: (authChecked) => set({ authChecked }),

  logout: () => {
    setToken(null)
    try { localStorage.removeItem('zs_session') } catch (_) {}
    set({ authToken: null, authUser: null, billingMe: null })
    get().reset()
  },

  // Session
  sessionId: null,

  // Flow
  step: 'idle',

  // Model info
  info: null,
  parts: [],          // array of {idx, name, face_count, vertex_count, is_watertight, bbox, dims}
  selectedPart: 0,

  // Auto cut state
  cutSuggestions: [],   // [{axis, position, score, crossing_count}]
  activeCutPlane: null, // {axis, position} — plano atualmente selecionado
  modelBounds: null,    // {min:[x,y,z], max:[x,y,z]}

  // Paint state
  paintMode: 'fill',  // 'brush' | 'fill' | 'smart'
  brushSize: 10,      // mm
  fillAngle: 5,       // degrees — conservador por padrão, evita vazar entre partes conectadas
  fillRadius: 100,    // mm — raio máximo 3D do flood fill (limita área por clique para undo granular)
  paintedFaces: [],   // flat array of face indices
  paintedCount: 0,
  undoStackSizes: [], // tamanho de cada entrada do histórico — para mostrar no botão Desfazer

  // Multi-cut: NOMES das partes já finalizadas. Rastreio por nome (não por
  // índice) — os índices do backend deslocam a cada novo corte, o nome não.
  completedNames: [],

  // Cut result
  cutOrigin: null,
  cutNormal: null,
  partAIdx: 0,
  partBIdx: 1,

  // Modo Professional (§1): máscara multi-peça
  maskLabels: null,        // Array de label por face | null
  maskRegionSizes: {},     // { regionId: nFaces }
  maskGranularity: 'media',
  selectedRegionId: null,  // região selecionada p/ split

  // Preview joints
  jointPins: [],      // array of pin descriptors
  jointParams: null,  // { n_pins, pin_diameter, pin_depth, tolerance, joint_type, fit }
  jointType: 'pin',   // 'pin' | 'ball' | 'dovetail'
  jointFit: 'flexivel', // 'flexivel' | 'apertado'
  selectedPinIdx: null, // conector selecionado p/ edição individual

  // Result
  warnings: [],

  // View
  viewMode: 'same',   // 'side' | 'tabs' | 'same'
  activeTab: 0,
  showWireframe: false,
  showGrid: true,
  showJoints: true,
  showXray: false,    // transparência p/ inspecionar folga macho/fêmea

  // Export
  exportFmt: 'stl',

  // UI state
  loading: false,
  progress: 0,
  progressMsg: '',
  error: null,

  // Lang (mirror for re-renders)
  lang: localStorage.getItem('zs_lang') || 'pt',

  // Theme
  theme: localStorage.getItem('zs_theme') || 'light',

  // Restore modal
  restorePrompt: null,  // { sessionId, info, parts, step } | null

  // ── Actions ─────────────────────────────────────────────────
  setLang: (l) => { localStorage.setItem('zs_lang', l); set({ lang: l }) },
  setTheme: (th) => { localStorage.setItem('zs_theme', th); set({ theme: th }) },

  setStep: (step) => set({ step }),

  setJointType: (jointType) => set({ jointType }),
  setJointFit: (jointFit) => set({ jointFit }),

  setLoading: (loading, msg = '', progress = 0) =>
    set({ loading, progressMsg: msg, progress }),

  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),

  afterUpload: (sessionId, info, parts) => {
    try {
      localStorage.setItem('zs_session', JSON.stringify({ sessionId, info, parts, step: 'loaded', paintedFaces: [], selectedPart: 0 }))
    } catch (_) {}
    set({ sessionId, info, parts, step: 'loaded', selectedPart: 0, paintedFaces: [], paintedCount: 0 })
  },

  _persistPaint: (paintedFaces) => {
    // Atualiza apenas paintedFaces + step no localStorage sem reescrever o objeto todo
    try {
      const raw = localStorage.getItem('zs_session')
      if (!raw) return
      const saved = JSON.parse(raw)
      saved.paintedFaces = paintedFaces
      saved.step = 'painting'
      saved.selectedPart = get().selectedPart
      localStorage.setItem('zs_session', JSON.stringify(saved))
    } catch (_) {}
  },

  afterSuggestCuts: (suggestions, bounds) =>
    set({ cutSuggestions: suggestions, modelBounds: bounds, step: 'cutting',
          activeCutPlane: suggestions.length ? { axis: suggestions[0].axis, position: suggestions[0].position } : null }),

  setActiveCutPlane: (axis, position) =>
    set({ activeCutPlane: { axis, position } }),

  afterAutoCut: (parts, cutOrigin, cutNormal, partAIdx, partBIdx) =>
    set({ parts, cutOrigin, cutNormal, partAIdx, partBIdx, step: 'previewing' }),

  afterPaintCut: (parts, cutOrigin, cutNormal, partAIdx, partBIdx) => {
    // Limpa paint do localStorage — o corte foi feito, não faz mais sentido restaurar
    try {
      const raw = localStorage.getItem('zs_session')
      if (raw) { const s = JSON.parse(raw); s.paintedFaces = []; s.step = 'previewing'; localStorage.setItem('zs_session', JSON.stringify(s)) }
    } catch (_) {}
    set({ parts, cutOrigin, cutNormal, partAIdx, partBIdx, step: 'previewing', paintedFaces: [], paintedCount: 0 })
  },

  afterPreview: (jointPins, jointParams) =>
    set({ jointPins, jointParams, step: 'previewing', selectedPinIdx: null }),

  afterConfirm: (parts, warnings) =>
    set({ parts, warnings, step: 'result', selectedPinIdx: null }),

  setSelectedPin: (selectedPinIdx) => set({ selectedPinIdx }),

  // Modo Professional (§1)
  afterSegmentMask: (labels, regionSizes, granularity) =>
    set({ maskLabels: labels, maskRegionSizes: regionSizes, maskGranularity: granularity,
          selectedRegionId: null, step: 'multimask' }),

  setSelectedRegion: (selectedRegionId) => set({ selectedRegionId }),

  exitMultiMask: () =>
    set({ maskLabels: null, maskRegionSizes: {}, selectedRegionId: null, step: 'loaded' }),

  afterMultiMaskCut: (parts) =>
    set({ parts, maskLabels: null, maskRegionSizes: {}, selectedRegionId: null,
          warnings: [], step: 'result' }),

  // Re-sincroniza `parts` com a sessão no backend (fonte da verdade — nunca
  // perde peças) e volta para a tela de montagem completa, sem descartar
  // nenhum corte/encaixe já feito.
  backToAssembly: (parts) =>
    set({
      parts, step: 'result', selectedPinIdx: null,
      maskLabels: null, maskRegionSizes: {}, selectedRegionId: null,
      paintedFaces: [], paintedCount: 0,
    }),

  // Descarta todos os cortes/encaixes da sessão e volta ao estado do upload.
  afterRestoreOriginal: (parts) =>
    set({
      parts, step: 'loaded', selectedPart: 0, completedNames: [],
      paintedFaces: [], paintedCount: 0, cutSuggestions: [], activeCutPlane: null,
      cutOrigin: null, cutNormal: null, maskLabels: null, maskRegionSizes: {},
      selectedRegionId: null, jointPins: [], jointParams: null, warnings: [],
      selectedPinIdx: null,
    }),

  // Edição individual (§2.2): aplica patch a um conector do preview
  updatePin: (idx, patch) => set(s => ({
    jointPins: s.jointPins.map((p, i) => (i === idx ? { ...p, ...patch } : p)),
  })),

  // Inicia um novo corte em uma das partes já geradas.
  // As demais partes são marcadas como prontas (por NOME); a parte escolhida
  // deixa de ser "pronta" caso estivesse.
  cutAgain: (partIdx) => {
    const { parts, completedNames } = get()
    const keepPart = parts.find(p => p.idx === partIdx)
    if (!keepPart) return
    const done = new Set(completedNames)
    for (const p of parts) if (p.idx !== partIdx) done.add(p.name)
    done.delete(keepPart.name)
    set({
      completedNames: [...done],
      parts: [keepPart],
      selectedPart: partIdx,
      paintedFaces: [],
      paintedCount: 0,
      step: 'painting',
      jointPins: [],
      jointParams: null,
      cutOrigin: null,
      cutNormal: null,
      maskLabels: null,
      maskRegionSizes: {},
      selectedRegionId: null,
    })
  },

  setPaintedFaces: (faces) =>
    set({ paintedFaces: faces, paintedCount: faces.length }),

  addPaintedFaces: (newFaces) => {
    const existing = new Set(get().paintedFaces)
    for (const f of newFaces) existing.add(f)
    const arr = [...existing]
    set({ paintedFaces: arr, paintedCount: arr.length })
    get()._persistPaint(arr)
  },

  removePaintedFaces: (faces) => {
    const toRemove = new Set(faces)
    const arr = get().paintedFaces.filter(f => !toRemove.has(f))
    set({ paintedFaces: arr, paintedCount: arr.length })
    get()._persistPaint(arr)
  },

  clearPaintedFaces: () => {
    set({ paintedFaces: [], paintedCount: 0, undoStackSizes: [] })
    get()._persistPaint([])
  },

  pushUndoEntry: (count) => set(s => ({ undoStackSizes: [...s.undoStackSizes, count] })),
  popUndoEntry: () => set(s => ({ undoStackSizes: s.undoStackSizes.slice(0, -1) })),

  reset: () => {
    try { localStorage.removeItem('zs_session') } catch (_) {}
    set({
      sessionId: null, step: 'idle', info: null, parts: [], completedNames: [],
      paintedFaces: [], paintedCount: 0, fillRadius: 40,
      cutSuggestions: [], activeCutPlane: null, modelBounds: null,
      cutOrigin: null, cutNormal: null,
      maskLabels: null, maskRegionSizes: {}, selectedRegionId: null,
      jointPins: [], jointParams: null, warnings: [],
      loading: false, error: null, restorePrompt: null,
      selectedPart: 0, viewMode: 'same', activeTab: 0,
      exportFmt: 'stl', progressMsg: '', progress: 0,
      showWireframe: false, partAIdx: 0, partBIdx: 1,
    })
  },

  dismissRestore: () => {
    try { localStorage.removeItem('zs_session') } catch (_) {}
    set({ restorePrompt: null })
  },

  setRestorePrompt: (data) => set({ restorePrompt: data }),

  restoreSession: (data) => {
    const paintedFaces = data.paintedFaces || []
    set({
      sessionId: data.sessionId,
      info: data.info,
      parts: data.parts,
      step: paintedFaces.length > 0 ? 'painting' : (data.step || 'loaded'),
      selectedPart: data.selectedPart ?? 0,
      paintedFaces,
      paintedCount: paintedFaces.length,
      restorePrompt: null,
    })
  },
}))
