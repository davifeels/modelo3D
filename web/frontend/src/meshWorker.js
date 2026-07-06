// Web Worker: expande geometria indexed → non-indexed fora da thread principal
// Sem imports — worker clássico compatível com todos os bundlers

self.onmessage = function (e) {
  const { buf, partIdx, baseR, baseG, baseB } = e.data

  try {
    const u32 = new Uint32Array(buf, 0, 2)
    const nVerts = u32[0]
    const nFaces = u32[1]
    let o = 8

    const vertices = new Float32Array(buf, o, nVerts * 3); o += nVerts * 12
    const faces    = new Uint32Array(buf,  o, nFaces * 3); o += nFaces * 12
    const normals  = new Float32Array(buf, o, nVerts * 3); o += nVerts * 12
    const centroid = new Float32Array(buf, o, 3);          o += 12
    const bboxMin  = new Float32Array(buf, o, 3);          o += 12
    const bboxMax  = new Float32Array(buf, o, 3);          o += 12
    const dv = new DataView(buf, o)
    const isWatertight = dv.getUint8(0) === 1
    const volumeCm3    = dv.getFloat32(1, true)

    const total = nFaces * 9
    const pos  = new Float32Array(total)
    const norm = new Float32Array(total)
    const col  = new Float32Array(total)

    // Loop desrolado: processa 1 face completa (3 vértices) por iteração
    for (let fi = 0; fi < nFaces; fi++) {
      const fi9 = fi * 9
      const fi3 = fi * 3

      const v0 = faces[fi3    ] * 3
      const v1 = faces[fi3 + 1] * 3
      const v2 = faces[fi3 + 2] * 3

      // Vértice 0
      pos[fi9]     = vertices[v0];     pos[fi9 + 1] = vertices[v0 + 1]; pos[fi9 + 2] = vertices[v0 + 2]
      norm[fi9]    = normals[v0];      norm[fi9 + 1] = normals[v0 + 1]; norm[fi9 + 2] = normals[v0 + 2]
      col[fi9]     = baseR;            col[fi9 + 1]  = baseG;           col[fi9 + 2]  = baseB

      // Vértice 1
      pos[fi9 + 3] = vertices[v1];     pos[fi9 + 4] = vertices[v1 + 1]; pos[fi9 + 5] = vertices[v1 + 2]
      norm[fi9 + 3] = normals[v1];     norm[fi9 + 4] = normals[v1 + 1]; norm[fi9 + 5] = normals[v1 + 2]
      col[fi9 + 3]  = baseR;           col[fi9 + 4]  = baseG;           col[fi9 + 5]  = baseB

      // Vértice 2
      pos[fi9 + 6] = vertices[v2];     pos[fi9 + 7] = vertices[v2 + 1]; pos[fi9 + 8] = vertices[v2 + 2]
      norm[fi9 + 6] = normals[v2];     norm[fi9 + 7] = normals[v2 + 1]; norm[fi9 + 8] = normals[v2 + 2]
      col[fi9 + 6]  = baseR;           col[fi9 + 7]  = baseG;           col[fi9 + 8]  = baseB
    }

    self.postMessage(
      { partIdx, pos, norm, col, nFaces, nVerts, isWatertight, volumeCm3,
        center: [centroid[0], centroid[1], centroid[2]],
        bboxMin: [bboxMin[0], bboxMin[1], bboxMin[2]],
        bboxMax: [bboxMax[0], bboxMax[1], bboxMax[2]] },
      [pos.buffer, norm.buffer, col.buffer]
    )
  } catch (err) {
    self.postMessage({ error: err.message, partIdx })
  }
}
