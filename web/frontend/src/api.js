const BASE = '/api'

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Erro desconhecido')
  }
  return res.json()
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
    const res = await fetch(`${BASE}/mesh-bin/${sessionId}/${partIdx}`)
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
    (name ? `?name=${encodeURIComponent(name)}` : ''),

  // names: { [partIdx]: "nome_editado" } — backend usa nos nomes internos do ZIP
  exportZipUrl: (sessionId, fmt, names) =>
    `${BASE}/export-zip/${sessionId}/${fmt}` +
    (names && Object.keys(names).length ? `?names=${encodeURIComponent(JSON.stringify(names))}` : ''),

  checkSession: (sessionId) =>
    req('GET', `/session/${sessionId}`),

  getInterfaces: (sessionId) =>
    req('GET', `/interfaces/${sessionId}`),

  confirmAll: (sessionId, jointType, fit) =>
    req('POST', '/confirm-all', { session_id: sessionId, joint_type: jointType, fit }),
}
