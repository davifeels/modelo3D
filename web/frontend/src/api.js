const BASE = '/api'

// ── Token de autenticação (JWT do backend) ──────────────────────────────────
export function getToken() {
  return localStorage.getItem('zs_token')
}
export function setToken(token) {
  if (token) localStorage.setItem('zs_token', token)
  else localStorage.removeItem('zs_token')
}

// Chamado no 401 — o gate do App observa e volta para a tela de login
let _onUnauthorized = null
export function onUnauthorized(fn) { _onUnauthorized = fn }

async function req(method, path, body) {
  const headers = body instanceof FormData ? {} : { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    if (res.status === 401 && _onUnauthorized) _onUnauthorized()
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const e = new Error(err.detail || 'Erro desconhecido')
    e.status = res.status
    throw e
  }
  return res.json()
}

// Links <a href> (downloads) não enviam headers — o backend aceita ?token=
function tokenQS(prefix = '?') {
  const token = getToken()
  return token ? `${prefix}token=${encodeURIComponent(token)}` : ''
}

export const api = {
  upload: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return req('POST', '/upload', fd)
  },

  getMesh: (sessionId, partIdx) =>
    req('GET', `/mesh/${sessionId}/${partIdx}`),

  getMeshBin: async (sessionId, partIdx) => {
    const token = getToken()
    const res = await fetch(`${BASE}/mesh-bin/${sessionId}/${partIdx}`,
      token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
    if (!res.ok) throw new Error('Erro ao carregar mesh binária')
    return res.arrayBuffer()
  },

  getMeshAdj: (sessionId, partIdx) =>
    req('GET', `/mesh-adj/${sessionId}/${partIdx}`),

  regionGrow: (sessionId, partIdx, point, angleDeg) =>
    req('POST', '/region-grow', { session_id: sessionId, part_idx: partIdx, point, angle_deg: angleDeg }),

  smartSelect: (sessionId, partIdx, faceIdx, maxPct = 0.6) =>
    req('POST', '/smart-select', {
      session_id: sessionId,
      part_idx: partIdx,
      face_idx: faceIdx,
      max_region_pct: maxPct,
    }),

  suggestCuts: (sessionId, partIdx = 0) =>
    req('POST', '/suggest-cuts', { session_id: sessionId, part_idx: partIdx, n_results: 5 }),

  cutFromPainted: (sessionId, partIdx, paintedFaceIndices) =>
    req('POST', '/cut-from-painted', { session_id: sessionId, part_idx: partIdx, painted_face_indices: paintedFaceIndices }),

  cut: (sessionId, partIdx, axis, position) =>
    req('POST', '/cut', { session_id: sessionId, part_idx: partIdx, axis, position }),

  splitComponents: (sessionId, partIdx) =>
    req('POST', '/split-components', { session_id: sessionId, part_idx: partIdx }),

  previewJoints: (sessionId, partAIdx, partBIdx, cutOrigin, cutNormal, jointType, fit) =>
    req('POST', '/preview-joints', {
      session_id: sessionId,
      part_a_idx: partAIdx,
      part_b_idx: partBIdx,
      cut_origin: cutOrigin,
      cut_normal: cutNormal,
      joint_type: jointType,
      fit,
    }),

  confirm: (sessionId, partAIdx, partBIdx, cutOrigin, cutNormal, jointType, fit, pins) =>
    req('POST', '/confirm', {
      session_id: sessionId,
      part_a_idx: partAIdx,
      part_b_idx: partBIdx,
      cut_origin: cutOrigin,
      cut_normal: cutNormal,
      joint_type: jointType,
      fit,
      pins,
    }),

  exportUrl: (sessionId, partIdx, fmt, name) =>
    `${BASE}/export/${sessionId}/${partIdx}/${fmt}` +
    (name ? `?name=${encodeURIComponent(name)}` : '') +
    tokenQS(name ? '&' : '?'),

  // names: { [partIdx]: "nome_editado" } — backend usa nos nomes internos do ZIP
  exportZipUrl: (sessionId, fmt, names) => {
    const hasNames = names && Object.keys(names).length
    return `${BASE}/export-zip/${sessionId}/${fmt}` +
      (hasNames ? `?names=${encodeURIComponent(JSON.stringify(names))}` : '') +
      tokenQS(hasNames ? '&' : '?')
  },

  checkSession: (sessionId) =>
    req('GET', `/session/${sessionId}`),

  getInterfaces: (sessionId) =>
    req('GET', `/interfaces/${sessionId}`),

  confirmAll: (sessionId, jointType, fit) =>
    req('POST', '/confirm-all', { session_id: sessionId, joint_type: jointType, fit }),

  // Modo Professional (§1): máscara multi-peça
  segmentMask: (sessionId, partIdx, granularity) =>
    req('POST', '/segment-mask', { session_id: sessionId, part_idx: partIdx, granularity }),

  maskSplit: (sessionId, partIdx, labels, regionId) =>
    req('POST', '/mask-split', { session_id: sessionId, part_idx: partIdx, labels, region_id: regionId }),

  cutByMultiMask: (sessionId, partIdx, labels) =>
    req('POST', '/cut-by-multi-mask', { session_id: sessionId, part_idx: partIdx, labels }),

  // ── Auth ──────────────────────────────────────────────────────────────────
  register: (email, password, name) =>
    req('POST', '/auth/register', { email, password, name }),

  login: (email, password) =>
    req('POST', '/auth/login', { email, password }),

  authMe: () => req('GET', '/auth/me'),

  // ── Billing ───────────────────────────────────────────────────────────────
  billingPlans: () => req('GET', '/billing/plans'),

  billingMe: () => req('GET', '/billing/me'),

  billingCheckout: (plano, periodo, paymentMethod) =>
    req('POST', '/billing/checkout', { plano, periodo, payment_method: paymentMethod }),

  billingCancel: () => req('POST', '/billing/cancel'),

  billingChangePlan: (plano, periodo) =>
    req('POST', '/billing/change-plan', { plano, periodo }),
}
