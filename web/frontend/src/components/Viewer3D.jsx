import { useEffect, useRef, useImperativeHandle, forwardRef, useCallback, useState } from 'react'
import * as THREE from 'three'
import { useStore } from '../store.js'
import { api } from '../api.js'
import { t, tf } from '../i18n.js'

// ── Cores ────────────────────────────────────────────────────────────────────
const C = {
  base: new THREE.Color(0x7080a0),
  painted: new THREE.Color(0xf97316),
  partA: new THREE.Color(0x3b82f6),
  partB: new THREE.Color(0xef4444),
  pin: new THREE.Color(0x2563eb),
  hole: new THREE.Color(0xdc2626),
  cutPlane: new THREE.Color(0x7c3aed),
  grid: 0x1a1a2e,
  bg: 0x0b0b12,
}

function getThemeColors(theme) {
  const isLight = theme === 'light'
  return {
    bg: isLight ? 0xf1f4f9 : 0x0b0b12,
    fog: isLight ? 0xf1f4f9 : 0x0b0b12,
    gridA: isLight ? 0xd0d8e8 : 0x1a1a2e,
    gridB: isLight ? 0xe2e8f4 : 0x16162a,
  }
}

// Paleta compartilhada com RightPanel/ExportPanel — indexada pelo idx da parte
const PART_COLORS = [
  C.partA, C.partB,
  new THREE.Color(0x10b981), new THREE.Color(0xf59e0b),
  new THREE.Color(0x8b5cf6), new THREE.Color(0x06b6d4),
  new THREE.Color(0xec4899), new THREE.Color(0x84cc16),
]

// ── OrbitControls inline (sem dependência extra) ──────────────────────────────
class OrbitControls {
  constructor(camera, domElement) {
    this.camera = camera
    this.el = domElement
    this.enabled = true
    this._state = 0 // 0=none 1=rotate 2=pan
    this._start = new THREE.Vector2()
    this._spherical = new THREE.Spherical()
    this._spherical.setFromVector3(camera.position)
    this._target = new THREE.Vector3()
    this._panDelta = new THREE.Vector3()

    this._onMouseDown = this._onMouseDown.bind(this)
    this._onMouseMove = this._onMouseMove.bind(this)
    this._onMouseUp = this._onMouseUp.bind(this)
    this._onWheel = this._onWheel.bind(this)

    domElement.addEventListener('mousedown', this._onMouseDown)
    domElement.addEventListener('mousemove', this._onMouseMove)
    domElement.addEventListener('mouseup', this._onMouseUp)
    domElement.addEventListener('wheel', this._onWheel, { passive: false })
  }

  _onMouseDown(e) {
    if (!this.enabled) return
    this._start.set(e.clientX, e.clientY)
    if (e.button === 0) {
      if (this.blockLeftClick) return  // painting mode: esquerdo vai para o raycaster
      this._state = 1  // rotate
    } else if (e.button === 2) {
      // Em painting mode, direito orbita. Fora dele, pan.
      this._state = this.blockLeftClick ? 1 : 2
    } else if (e.button === 1) {
      this._state = 2  // meio sempre faz pan
    }
  }

  _onMouseMove(e) {
    if (!this.enabled || this._state === 0) return
    const dx = e.clientX - this._start.x
    const dy = e.clientY - this._start.y
    this._start.set(e.clientX, e.clientY)

    if (this._state === 1) {
      this._spherical.theta -= dx * 0.005
      this._spherical.phi -= dy * 0.005
      this._spherical.phi = Math.max(0.05, Math.min(Math.PI - 0.05, this._spherical.phi))
    } else if (this._state === 2) {
      const scale = this._spherical.radius * 0.001
      this._panDelta.set(-dx * scale, dy * scale, 0).applyQuaternion(this.camera.quaternion)
      this._target.add(this._panDelta)
    }
    this._updateCamera()
    this.onUserChange?.()
  }

  _onMouseUp() { this._state = 0 }

  _onWheel(e) {
    if (!this.enabled) return
    e.preventDefault()
    this._spherical.radius *= e.deltaY > 0 ? 1.1 : 0.9
    this._spherical.radius = Math.max(1, Math.min(5000, this._spherical.radius))
    this._updateCamera()
    this.onUserChange?.()
  }

  // Copia o estado de câmera de outro controls (sync entre viewports)
  syncFrom(other) {
    this._spherical.radius = other._spherical.radius
    this._spherical.theta = other._spherical.theta
    this._spherical.phi = other._spherical.phi
    this._target.copy(other._target)
    this._updateCamera()
  }

  _updateCamera() {
    const pos = new THREE.Vector3().setFromSpherical(this._spherical).add(this._target)
    this.camera.position.copy(pos)
    this.camera.lookAt(this._target)
  }

  setTarget(v) {
    this._target.copy(v)
    this._updateCamera()
  }

  reset(pos, target) {
    this._target.copy(target)
    this._spherical.setFromVector3(pos.clone().sub(target))
    this._updateCamera()
  }

  dispose() {
    this.el.removeEventListener('mousedown', this._onMouseDown)
    this.el.removeEventListener('mousemove', this._onMouseMove)
    this.el.removeEventListener('mouseup', this._onMouseUp)
    this.el.removeEventListener('wheel', this._onWheel)
  }
}

// ── Sincronização de câmera entre viewports (modo lado a lado) ────────────────
// Pub/sub leve: cada instância publica interações do usuário; as demais copiam.
const _camSyncListeners = new Set()
function _camSyncPublish(srcControls) {
  for (const fn of _camSyncListeners) fn(srcControls)
}

// ── Parse binary mesh buffer e constrói geometria Three.js ───────────────────
//
// Layout binário (little-endian, gerado por session.py::mesh_to_binary):
//   [u32 nVerts][u32 nFaces]
//   [float32 * nVerts*3] vertices
//   [u32 * nFaces*3]     faces
//   [float32 * nVerts*3] normals
//   [float32 * 3]        centroid
//   [float32 * 3]        bbox_min
//   [float32 * 3]        bbox_max
//   [u8 isWatertight][float32 volumeCm3]
//
function parseMeshBin(buf) {
  const header = new Uint32Array(buf, 0, 2)
  const nVerts = header[0]
  const nFaces = header[1]
  let o = 8

  // Zero-copy views diretamente no ArrayBuffer
  const vertices = new Float32Array(buf, o, nVerts * 3); o += nVerts * 12
  const faces    = new Uint32Array(buf,  o, nFaces * 3); o += nFaces * 12
  const normals  = new Float32Array(buf, o, nVerts * 3); o += nVerts * 12
  const centroid = new Float32Array(buf, o, 3);          o += 12
  const bboxMin  = new Float32Array(buf, o, 3);          o += 12
  const bboxMax  = new Float32Array(buf, o, 3);          o += 12
  const dv = new DataView(buf, o)
  const isWatertight = dv.getUint8(0) === 1
  const volumeCm3 = dv.getFloat32(1, true)

  // Expande indexed → non-indexed (necessário para pintura por face)
  const pos  = new Float32Array(nFaces * 9)
  const norm = new Float32Array(nFaces * 9)
  const col  = new Float32Array(nFaces * 9)

  for (let fi = 0; fi < nFaces; fi++) {
    const fi3 = fi * 3
    for (let vi = 0; vi < 3; vi++) {
      const src = faces[fi3 + vi] * 3
      const dst = (fi3 + vi) * 3
      pos[dst]     = vertices[src];     pos[dst + 1] = vertices[src + 1]; pos[dst + 2] = vertices[src + 2]
      norm[dst]    = normals[src];      norm[dst + 1] = normals[src + 1]; norm[dst + 2] = normals[src + 2]
      col[dst]     = C.base.r;          col[dst + 1]  = C.base.g;         col[dst + 2]  = C.base.b
    }
  }

  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.setAttribute('normal',   new THREE.BufferAttribute(norm, 3))
  geo.setAttribute('color',    new THREE.BufferAttribute(col, 3))
  geo._faceCount = nFaces

  return {
    geo,
    meshData: {
      vertices, faces, normals,
      center: Array.from(centroid),
      bbox: { min: Array.from(bboxMin), max: Array.from(bboxMax) },
      is_watertight: isWatertight,
      volume_cm3: isWatertight ? volumeCm3 : null,
      face_count: nFaces,
      vertex_count: nVerts,
    },
  }
}

function buildGeometry(meshData) {
  const vArr = meshData.vertices instanceof Float32Array ? meshData.vertices : new Float32Array(meshData.vertices)
  const fArr = meshData.faces instanceof Uint32Array ? meshData.faces : new Uint32Array(meshData.faces)
  const nArr = meshData.normals instanceof Float32Array ? meshData.normals : new Float32Array(meshData.normals)
  const faceCount = fArr.length / 3
  const pos  = new Float32Array(faceCount * 9)
  const norm = new Float32Array(faceCount * 9)
  const col  = new Float32Array(faceCount * 9)
  for (let fi = 0; fi < faceCount; fi++) {
    const fi3 = fi * 3
    for (let vi = 0; vi < 3; vi++) {
      const src = fArr[fi3 + vi] * 3
      const dst = (fi3 + vi) * 3
      pos[dst]  = vArr[src];  pos[dst+1]  = vArr[src+1];  pos[dst+2]  = vArr[src+2]
      norm[dst] = nArr[src]; norm[dst+1] = nArr[src+1]; norm[dst+2] = nArr[src+2]
      col[dst]  = C.base.r;  col[dst+1]  = C.base.g;    col[dst+2]  = C.base.b
    }
  }
  const geo = new THREE.BufferGeometry()
  // Computa face normals (média das 3 vertex normals) para flood fill com critério global
  const faceNormals = new Float32Array(faceCount * 3)
  for (let fi = 0; fi < faceCount; fi++) {
    const base = fi * 9
    let nx = norm[base] + norm[base+3] + norm[base+6]
    let ny = norm[base+1] + norm[base+4] + norm[base+7]
    let nz = norm[base+2] + norm[base+5] + norm[base+8]
    const len = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1
    faceNormals[fi*3]   = nx / len
    faceNormals[fi*3+1] = ny / len
    faceNormals[fi*3+2] = nz / len
  }

  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.setAttribute('normal',   new THREE.BufferAttribute(norm, 3))
  geo.setAttribute('color',    new THREE.BufferAttribute(col, 3))
  geo._faceCount = faceCount
  geo._faceNormals = faceNormals  // usado pelo flood fill
  return geo
}

// ── Remove fragmentos flutuantes da seleção ───────────────────────────────────
// Dado um set de faces selecionadas e o grafo de adjacência completo,
// retorna apenas as faces que pertencem ao maior componente conectado.
// seedFace: face clicada — retorna o componente que contém o seed, não o maior.
// Isso garante que se o fill vazar para outra área maior (ex: tronco quando
// o usuário clicou no braço), retornamos o braço, não o tronco.
function keepSeedComponent(selectedSet, adjacency, seedFace) {
  const neighbors = new Map()
  for (const f of selectedSet) neighbors.set(f, [])
  for (let i = 0; i < adjacency.length; i++) {
    const [a, b] = adjacency[i]
    if (selectedSet.has(a) && selectedSet.has(b)) {
      neighbors.get(a).push(b)
      neighbors.get(b).push(a)
    }
  }
  // BFS a partir do seed
  const visited = new Set()
  const queue = [seedFace]
  while (queue.length) {
    const f = queue.pop()
    if (visited.has(f)) continue
    visited.add(f)
    for (const nb of (neighbors.get(f) || [])) {
      if (!visited.has(nb)) queue.push(nb)
    }
  }
  return [...visited]
}

// Legacy — mantida para compatibilidade com fillPaintGaps
function keepLargestComponent(selectedSet, adjacency, adjacencyAngles, angleThreshRad) {
  const neighbors = new Map()
  for (const f of selectedSet) neighbors.set(f, [])
  for (let i = 0; i < adjacency.length; i++) {
    const [a, b] = adjacency[i]
    if (selectedSet.has(a) && selectedSet.has(b)) {
      neighbors.get(a).push(b)
      neighbors.get(b).push(a)
    }
  }
  const visited = new Set()
  let largestComponent = []
  for (const start of selectedSet) {
    if (visited.has(start)) continue
    const component = []
    const queue = [start]
    while (queue.length) {
      const f = queue.pop()
      if (visited.has(f)) continue
      visited.add(f)
      component.push(f)
      for (const nb of (neighbors.get(f) || [])) {
        if (!visited.has(nb)) queue.push(nb)
      }
    }
    if (component.length > largestComponent.length) largestComponent = component
  }

  return largestComponent
}

// Filtra faces que estão além de maxRadius mm do centro da face semente.
// posArray = geometry.attributes.position.array (non-indexed, 9 floats por face)
function filterByRadius(faces, posArray, seedFaceIdx, maxRadius) {
  const si = seedFaceIdx * 9
  const sx = (posArray[si]   + posArray[si+3] + posArray[si+6]) / 3
  const sy = (posArray[si+1] + posArray[si+4] + posArray[si+7]) / 3
  const sz = (posArray[si+2] + posArray[si+5] + posArray[si+8]) / 3
  const r2 = maxRadius * maxRadius
  return faces.filter(fi => {
    const bi = fi * 9
    const dx = (posArray[bi]   + posArray[bi+3] + posArray[bi+6]) / 3 - sx
    const dy = (posArray[bi+1] + posArray[bi+4] + posArray[bi+7]) / 3 - sy
    const dz = (posArray[bi+2] + posArray[bi+5] + posArray[bi+8]) / 3 - sz
    return dx*dx + dy*dy + dz*dz <= r2
  })
}

// Versão que usa um ponto 3D explícito como centro (mais precisa para hit.point)
function filterByRadiusPoint(faces, posArray, center, maxRadius) {
  const r2 = maxRadius * maxRadius
  return faces.filter(fi => {
    const bi = fi * 9
    const dx = (posArray[bi]   + posArray[bi+3] + posArray[bi+6]) / 3 - center.x
    const dy = (posArray[bi+1] + posArray[bi+4] + posArray[bi+7]) / 3 - center.y
    const dz = (posArray[bi+2] + posArray[bi+5] + posArray[bi+8]) / 3 - center.z
    return dx*dx + dy*dy + dz*dz <= r2
  })
}


// ── Flood fill client-side ────────────────────────────────────────────────────
// Critério duplo:
//   1. ângulo diedro entre faces ADJACENTES < threshold (continuidade local)
//   2. ângulo entre normal da face candidata e normal da face SEED < threshold*2 (curvatura global)
// O critério 2 é o que faz o flood fill parar no contorno do olho num modelo orgânico suave,
// onde o critério 1 sozinho falha porque todos os ângulos locais são minúsculos.
// Flood fill por ângulo diedro — expande para faces com transição suave (< angleThreshRad).
// O raio euclidiano é aplicado DEPOIS como filtro espacial (não aqui).
// O critério hemisférico evita cruzar para o lado oposto do modelo.
function floodFill(startFace, adjacency, adjacencyAngles, angleThreshRad, faceNormals) {
  const visited = new Set()
  const stack = [startFace]

  // Normal da face seed — critério hemisférico
  const seedNx = faceNormals ? faceNormals[startFace * 3]     : null
  const seedNy = faceNormals ? faceNormals[startFace * 3 + 1] : null
  const seedNz = faceNormals ? faceNormals[startFace * 3 + 2] : null

  // Adjacency map filtrada pelo ângulo diedro
  const map = []
  for (let i = 0; i < adjacency.length; i++) {
    const [a, b] = adjacency[i]
    if (!map[a]) map[a] = []
    if (!map[b]) map[b] = []
    if (adjacencyAngles[i] < angleThreshRad) {
      map[a].push(b)
      map[b].push(a)
    }
  }

  while (stack.length) {
    const f = stack.pop()
    if (visited.has(f)) continue

    // Descarta faces apontando para o hemisfério oposto ao seed (evita pintar costas por frente)
    if (faceNormals && seedNx !== null) {
      const nx = faceNormals[f * 3], ny = faceNormals[f * 3 + 1], nz = faceNormals[f * 3 + 2]
      if (nx * seedNx + ny * seedNy + nz * seedNz < 0) continue
    }

    visited.add(f)
    for (const nb of (map[f] || [])) {
      if (!visited.has(nb)) stack.push(nb)
    }
  }
  return [...visited]
}

// ── Component ────────────────────────────────────────────────────────────────
const Viewer3D = forwardRef(function Viewer3D({ mode = 'single', paneIdx }, ref) {
  const [meshLoading, setMeshLoading] = useState(false)
  const [loadProgress, setLoadProgress] = useState('')
  const canvasRef = useRef()
  const sceneRef = useRef()
  const camRef = useRef()
  const rendRef = useRef()
  const controlsRef = useRef()
  const meshObjsRef = useRef([])  // THREE.Mesh objects
  const meshDataRef = useRef([])  // raw mesh data from server
  const paintHistRef = useRef([]) // undo history
  const rafRef = useRef()
  const brushCursorRef = useRef()
  const cutPlaneRef = useRef()
  const pinPreviewRef = useRef([])
  const overlayGroupRef = useRef()   // grupo Z-up p/ overlays em mesh space
  const gridRef = useRef()

  const theme = useStore(s => s.theme)

  const {
    step, sessionId, parts, selectedPart,
    paintMode, brushSize, fillAngle, fillRadius,
    showWireframe, showGrid, showJoints, showXray,
    jointPins, cutOrigin, cutNormal, selectedPinIdx,
    partAIdx, partBIdx,
    activeCutPlane, modelBounds,
    addPaintedFaces, removePaintedFaces, clearPaintedFaces, setError,
  } = useStore()

  // ── Reagir a mudança de tema ──────────────────────────────────────────────
  useEffect(() => {
    if (!rendRef.current || !sceneRef.current) return
    const tc = getThemeColors(theme)
    rendRef.current.setClearColor(tc.bg)
    if (sceneRef.current.fog) {
      sceneRef.current.fog.color.setHex(tc.fog)
    }
    if (gridRef.current) {
      gridRef.current.material[0] && (gridRef.current.material[0].color.setHex(tc.gridA))
      gridRef.current.material[1] && (gridRef.current.material[1].color.setHex(tc.gridB))
    }
  }, [theme])

  // ── Expose imperative API ─────────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    fitView: () => fitView(),
    clearPaint: () => clearPaintOnMesh(),
    undoPaint: () => undoPaint(),
    resetCamera: () => fitView(),
    fillPaintGaps: () => fillPaintGaps().catch(() => {}),
  }))

  // ── Setup scene ───────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current
    const W = canvas.clientWidth, H = canvas.clientHeight

    // Renderer
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(W, H, false)
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    const tc = getThemeColors(useStore.getState().theme)
    renderer.setClearColor(tc.bg)
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.1
    rendRef.current = renderer

    // Scene
    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(tc.fog, 0.004)
    sceneRef.current = scene

    // Grupo de overlays em coordenadas do BACKEND (mesh space, Z-up):
    // mesma rotação aplicada às partes — pinos/planos entram aqui com
    // as coordenadas cruas da API e ficam alinhados às malhas.
    const overlayGroup = new THREE.Group()
    overlayGroup.rotation.x = -Math.PI / 2
    scene.add(overlayGroup)
    overlayGroupRef.current = overlayGroup

    // Grid
    const grid = new THREE.GridHelper(300, 60, tc.gridA, tc.gridB)
    grid.position.y = -0.5
    scene.add(grid)
    gridRef.current = grid

    // Luzes — estúdio 3 pontos
    const ambient = new THREE.AmbientLight(0x8090b0, 0.8)
    scene.add(ambient)

    // Key light (principal — quente)
    const key = new THREE.DirectionalLight(0xffeedd, 1.6)
    key.position.set(80, 140, 80)
    key.castShadow = true
    key.shadow.mapSize.width = 2048
    key.shadow.mapSize.height = 2048
    key.shadow.camera.near = 1
    key.shadow.camera.far = 600
    key.shadow.camera.left = -150
    key.shadow.camera.right = 150
    key.shadow.camera.top = 150
    key.shadow.camera.bottom = -150
    key.shadow.bias = -0.001
    scene.add(key)

    // Fill light (fria, suave)
    const fill = new THREE.DirectionalLight(0xaabbff, 0.4)
    fill.position.set(-80, 60, -60)
    scene.add(fill)

    // Rim light (contorno)
    const rim = new THREE.DirectionalLight(0x9966ff, 0.25)
    rim.position.set(0, -30, -120)
    scene.add(rim)

    // Camera
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 10000)
    camera.position.set(0, 80, 200)
    camera.lookAt(0, 0, 0)
    camRef.current = camera

    // Controls
    const controls = new OrbitControls(camera, canvas)
    controlsRef.current = controls

    // Câmeras sincronizadas no modo lado a lado (paneIdx 0/1)
    let syncListener = null
    if (paneIdx !== undefined) {
      controls.onUserChange = () => _camSyncPublish(controls)
      syncListener = (src) => { if (src !== controls) controls.syncFrom(src) }
      _camSyncListeners.add(syncListener)
    }

    // Brush cursor (ring)
    const cursorGeo = new THREE.RingGeometry(0.95, 1.0, 32)
    const cursorMat = new THREE.MeshBasicMaterial({
      color: 0x2563eb, side: THREE.DoubleSide, depthTest: false, transparent: true, opacity: 0.8
    })
    const cursor = new THREE.Mesh(cursorGeo, cursorMat)
    cursor.visible = false
    cursor.renderOrder = 999
    scene.add(cursor)
    brushCursorRef.current = cursor

    // Resize observer
    const ro = new ResizeObserver(() => {
      const W2 = canvas.clientWidth, H2 = canvas.clientHeight
      renderer.setSize(W2, H2, false)
      camera.aspect = W2 / H2
      camera.updateProjectionMatrix()
    })
    ro.observe(canvas)

    // Render loop
    function animate() {
      rafRef.current = requestAnimationFrame(animate)
      renderer.render(scene, camera)
    }
    animate()

    return () => {
      cancelAnimationFrame(rafRef.current)
      ro.disconnect()
      if (syncListener) _camSyncListeners.delete(syncListener)
      controlsRef.current.dispose()
      renderer.dispose()
    }
  }, [])

  // ── Load meshes when parts change ─────────────────────────────────────────
  useEffect(() => {
    if (!sessionId || !parts.length || !sceneRef.current) return
    loadMeshes()
  }, [sessionId, parts])

  async function loadMeshes() {
    setMeshLoading(true)
    setLoadProgress(t('loading_geometry'))

    for (const m of meshObjsRef.current) {
      sceneRef.current.remove(m)
      m.geometry.dispose()
      m.material.dispose()
    }
    meshObjsRef.current = []
    meshDataRef.current = []

    try {
      // 1. Busca todos os binários em paralelo
      const buffers = await Promise.all(
        parts.map(async p => {
          try {
            return { bin: await api.getMeshBin(sessionId, p.idx) }
          } catch {
            try { return { json: await api.getMesh(sessionId, p.idx) } }
            catch { return null }
          }
        })
      )

      if (!sceneRef.current) return

      const currentStep = useStore.getState().step

      // 2. Processa geometria em Web Workers (não trava a UI)
      const processed = await Promise.all(
        buffers.map((result, i) => {
          if (!result) return Promise.resolve(null)
          if (result.json) {
            // Fallback síncrono para JSON
            return Promise.resolve({ geo: buildGeometry(result.json), meshData: result.json, idx: i })
          }
          // Binário → Web Worker
          const color = (currentStep === 'result' || currentStep === 'previewing')
            ? (PART_COLORS[i] || C.base)
            : C.base
          return new Promise((resolve, reject) => {
            const worker = new Worker(new URL('../meshWorker.js', import.meta.url))
            // Mostra progresso enquanto Worker processa
            const u32 = new Uint32Array(result.bin.slice(0, 8))
            const nf = u32[1]
            setLoadProgress(tf('processing_faces', { n: nf.toLocaleString() }))
            worker.onmessage = (e) => {
              worker.terminate()
              setLoadProgress('')
              if (e.data.error) { reject(new Error(e.data.error)); return }
              const { pos, norm, col, nFaces, center, bboxMin, bboxMax, isWatertight, volumeCm3, nVerts } = e.data
              const geo = new THREE.BufferGeometry()
              geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
              geo.setAttribute('normal',   new THREE.BufferAttribute(norm, 3))
              geo.setAttribute('color',    new THREE.BufferAttribute(col, 3))
              geo._faceCount = nFaces
              // Computa face normals para o critério global do flood fill
              const fn = new Float32Array(nFaces * 3)
              for (let fi = 0; fi < nFaces; fi++) {
                const b = fi * 9
                let nx = norm[b] + norm[b+3] + norm[b+6]
                let ny = norm[b+1] + norm[b+4] + norm[b+7]
                let nz = norm[b+2] + norm[b+5] + norm[b+8]
                const len = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1
                fn[fi*3] = nx/len; fn[fi*3+1] = ny/len; fn[fi*3+2] = nz/len
              }
              geo._faceNormals = fn
              resolve({
                geo,
                meshData: {
                  center, is_watertight: isWatertight,
                  volume_cm3: isWatertight ? volumeCm3 : null,
                  face_count: nFaces, vertex_count: nVerts,
                  bbox: { min: bboxMin, max: bboxMax },
                },
                idx: i,
              })
            }
            worker.onerror = (e) => { worker.terminate(); reject(e) }
            worker.postMessage(
              { buf: result.bin, partIdx: i, baseR: color.r, baseG: color.g, baseB: color.b },
              [result.bin]
            )
          })
        })
      )

      if (!sceneRef.current) return

      const newMeshes = []
      const newData   = []

      for (let i = 0; i < processed.length; i++) {
        const p = processed[i]
        if (!p) continue

        const color = (currentStep === 'result' || currentStep === 'previewing')
          ? (PART_COLORS[i] || new THREE.Color(0x888888))
          : C.base

        const mat = new THREE.MeshPhongMaterial({
          vertexColors: true, shininess: 60,
          specular: new THREE.Color(0x334466), side: THREE.DoubleSide,
          polygonOffset: true,
          polygonOffsetFactor: i,   // separa cada parte no depth buffer, elimina z-fighting
          polygonOffsetUnits: i,
        })
        colorFaces(p.geo, null, color)

        const mesh = new THREE.Mesh(p.geo, mat)
        mesh.userData.partIdx = i
        mesh.castShadow = true
        mesh.receiveShadow = true
        mesh.rotation.x = -Math.PI / 2
        mesh.userData.zUpRotated = true

        newMeshes.push(mesh)
        newData.push(p.meshData)
      }

      for (const mesh of newMeshes) sceneRef.current.add(mesh)
      meshObjsRef.current = newMeshes
      meshDataRef.current = newData

      fitView()
      // Segundo fitView após o primeiro render garante bbox correta
      requestAnimationFrame(() => fitView())
      showWireframeMode(showWireframe)
      showXrayMode(useStore.getState().showXray)
      if (step === 'previewing') updatePinPreview()

      // Restaura pintura após reload (paintedFaces persistido no localStorage)
      const { paintedFaces: restored, step: restoredStep } = useStore.getState()
      if (restoredStep === 'painting' && restored.length > 0 && meshObjsRef.current[0]) {
        colorFaces(meshObjsRef.current[0].geometry, restored, C.painted)
        paintHistRef.current = [restored]  // um único entry de undo para o estado restaurado
      }
    } finally {
      setMeshLoading(false)
    }
  }

  // ── Color helpers ─────────────────────────────────────────────────────────
  function colorFaces(geo, faceIndices, color) {
    const col = geo.attributes.color
    const arr = col.array
    const faceCount = geo._faceCount

    const r = color.r, g = color.g, b = color.b
    const targets = faceIndices ?? Array.from({ length: faceCount }, (_, i) => i)

    for (const fi of targets) {
      for (let vi = 0; vi < 3; vi++) {
        const off = (fi * 3 + vi) * 3
        arr[off] = r; arr[off + 1] = g; arr[off + 2] = b
      }
    }
    col.needsUpdate = true
  }

  // ── Paint face on mesh ────────────────────────────────────────────────────
  function paintFace(faceIdx, meshIdx = 0) {
    const geo = meshObjsRef.current[meshIdx]?.geometry
    if (!geo) return
    colorFaces(geo, [faceIdx], C.painted)
    addPaintedFaces([faceIdx])
  }

  function clearPaintOnMesh() {
    if (!meshObjsRef.current[0]) return
    const geo = meshObjsRef.current[0].geometry
    colorFaces(geo, null, C.base)  // BUG7 fix: usar C.base não PART_COLORS[0]
    clearPaintedFaces()
    paintHistRef.current = []
  }

  function undoPaint() {
    if (!paintHistRef.current.length) return
    const last = paintHistRef.current.pop()
    const geo = meshObjsRef.current[0]?.geometry
    if (!geo) return
    colorFaces(geo, last, C.base)
    removePaintedFaces(last)
  }

  async function fillPaintGaps() {
    // Fechamento morfológico: pinta faces não pintadas cercadas por vizinhos pintados.
    // Resolve triângulos "ilhados" que o flood fill pulou por ângulo alto local.
    const geo = meshObjsRef.current[0]?.geometry
    const data = meshDataRef.current[0]
    if (!geo || !data) return

    // Lazy-load adjacency (pode não ter sido carregada se só usou pincel)
    if (!data.face_adjacency) {
      const { sessionId, selectedPart } = useStore.getState()
      try {
        const adj = await api.getMeshAdj(sessionId, selectedPart)
        data.face_adjacency = adj.face_adjacency
        data.face_adjacency_angles = adj.face_adjacency_angles
      } catch (_) { return }
    }
    if (!data.face_adjacency) return

    const painted = new Set(useStore.getState().paintedFaces)
    const adj = data.face_adjacency
    const totalFaces = geo.attributes.position.count / 3

    // Constrói mapa de adjacência face → vizinhos
    const neighbors = new Map()
    for (const [a, b] of adj) {
      if (!neighbors.has(a)) neighbors.set(a, [])
      if (!neighbors.has(b)) neighbors.set(b, [])
      neighbors.get(a).push(b)
      neighbors.get(b).push(a)
    }

    // Limite generoso: até 3% das faces ou 100 — cobre seams visíveis
    const maxGapSize = Math.max(100, Math.floor(totalFaces * 0.03))

    const visited = new Set()
    const toFill = []

    for (let face = 0; face < totalFaces; face++) {
      if (painted.has(face) || visited.has(face)) continue

      // BFS — coleta o componente de faces não-pintadas
      const component = []
      const queue = [face]
      visited.add(face)
      let paintedBorder = 0
      let totalBorder = 0
      let tooLarge = false

      while (queue.length) {
        const f = queue.shift()
        component.push(f)
        for (const nb of (neighbors.get(f) || [])) {
          if (painted.has(nb)) { paintedBorder++; totalBorder++; continue }
          totalBorder++
          if (visited.has(nb)) continue
          visited.add(nb)
          queue.push(nb)
        }
        if (component.length > maxGapSize) { tooLarge = true; break }
      }

      if (tooLarge) continue

      // Preenche se a maioria da borda (≥ 60%) está pintada — falha dentro de região pintada
      const borderRatio = totalBorder > 0 ? paintedBorder / totalBorder : 0
      if (borderRatio >= 0.6) {
        for (const f of component) { painted.add(f); toFill.push(f) }
      }
    }

    if (!toFill.length) return
    colorFaces(geo, toFill, C.painted)
    paintHistRef.current.push(toFill)
    addPaintedFaces(toFill)
  }

  // Converte ponto do espaço da cena para espaço original do mesh (desfaz rotação Z-up)
  function toMeshSpace(point, meshIdx) {
    const meshObj = meshObjsRef.current[meshIdx]
    if (!meshObj?.userData.zUpRotated) return [point.x, point.y, point.z]
    // Desfaz rotation.x = -PI/2: x=x, y=-z, z=y
    return [point.x, -point.z, point.y]
  }

  // ── Raycasting ────────────────────────────────────────────────────────────
  function getRaycastFace(e) {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1
    const raycaster = new THREE.Raycaster()
    raycaster.setFromCamera({ x, y }, camRef.current)
    const hits = raycaster.intersectObjects(meshObjsRef.current)
    if (!hits.length) return null

    // Filtra por faces voltadas para a câmera (evita acertar faces internas/traseiras)
    const camDir = new THREE.Vector3()
    camRef.current.getWorldDirection(camDir)
    const frontHit = hits.find(h => {
      const n = h.face?.normal?.clone()
      if (!n) return true
      // Normal no espaço do mundo
      const normalWorld = n.transformDirection(h.object.matrixWorld)
      // Face voltada para câmera: normal aponta CONTRA a direção de visão
      return normalWorld.dot(camDir) < 0
    })
    if (!frontHit) return null
    return { hit: frontHit, meshIdx: meshObjsRef.current.indexOf(frontHit.object) }
  }

  // ── Brush: find faces within radius ──────────────────────────────────────
  function getFacesInRadius(hit, meshIdx, radiusMM) {
    const geo = meshObjsRef.current[meshIdx]?.geometry
    const meshObj = meshObjsRef.current[meshIdx]
    if (!geo || !meshObj) return []
    const pos = geo.attributes.position.array
    const norm = geo.attributes.normal?.array
    const faceCount = geo._faceCount
    // Transforma hit.point (world space) para local space da geometria
    const invMat = meshObj.matrixWorld.clone().invert()
    const localCenter = hit.point.clone().applyMatrix4(invMat)
    // Normal da face clicada já está em local space da geometria — não transforma
    const hitNormal = hit.face.normal
    const r2 = radiusMM * radiusMM
    const result = []
    for (let fi = 0; fi < faceCount; fi++) {
      const off = fi * 9
      const cx = (pos[off] + pos[off + 3] + pos[off + 6]) / 3
      const cy = (pos[off + 1] + pos[off + 4] + pos[off + 7]) / 3
      const cz = (pos[off + 2] + pos[off + 5] + pos[off + 8]) / 3
      const dx = cx - localCenter.x, dy = cy - localCenter.y, dz = cz - localCenter.z
      if (dx * dx + dy * dy + dz * dz >= r2) continue
      // Filtra faces do lado oposto — dot < 0 = normal apontando para lado contrário
      if (norm) {
        const ni = fi * 9
        const nx = (norm[ni] + norm[ni+3] + norm[ni+6]) / 3
        const ny = (norm[ni+1] + norm[ni+4] + norm[ni+7]) / 3
        const nz = (norm[ni+2] + norm[ni+5] + norm[ni+8]) / 3
        if (nx * hitNormal.x + ny * hitNormal.y + nz * hitNormal.z < 0) continue
      }
      result.push(fi)
    }
    return result
  }

  // ── Brush cursor ──────────────────────────────────────────────────────────
  function updateBrushCursor(e) {
    const cursor = brushCursorRef.current
    if (!cursor) return
    const res = getRaycastFace(e)
    if (!res) { cursor.visible = false; return }
    const { hit } = res
    cursor.visible = true
    // Transforma normal local → world space
    const worldNormal = hit.face.normal.clone()
      .transformDirection(hit.object.matrixWorld)
      .normalize()
    cursor.position.copy(hit.point)
    cursor.position.addScaledVector(worldNormal, 0.3)
    cursor.lookAt(hit.point.clone().add(worldNormal))
    const { brushSize: currentBrushSizeCursor, paintMode: currentModeCursor } = useStore.getState()
    cursor.material.color.setHex(currentModeCursor === 'eraser' ? 0xf97316 : 0x2563eb)
    cursor.scale.set(currentBrushSizeCursor, currentBrushSizeCursor, currentBrushSizeCursor)
  }

  // ── Seleção de conector no preview (§2.2) ────────────────────────────────
  const pinPickDownRef = useRef(null)

  function pickPinAt(e) {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1
    const raycaster = new THREE.Raycaster()
    raycaster.setFromCamera({ x, y }, camRef.current)
    const hits = raycaster.intersectObjects(pinPreviewRef.current)
    const idx = hits.length ? hits[0].object.userData.pinIdx : null
    useStore.getState().setSelectedPin(idx ?? null)
  }

  // ── Mouse events ──────────────────────────────────────────────────────────
  const isPainting = useRef(false)
  const isProcessingFill = useRef(false) // guard contra cliques simultâneos no conta-gotas
  const brushBatchRef = useRef(new Set()) // acumula faces do drag atual — push em onMouseUp

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    function onMouseDown(e) {
      if (e.button === 0) pinPickDownRef.current = { x: e.clientX, y: e.clientY }
      if (step !== 'painting' || e.button !== 0) return
      e.preventDefault()
      isPainting.current = true
      handlePaintClick(e)
    }

    function onMouseMove(e) {
      if (step !== 'painting') return
      if (paintMode === 'brush' || paintMode === 'eraser') {
        updateBrushCursor(e)
        if (isPainting.current) handleBrushStroke(e)
      } else {
        const cursor = brushCursorRef.current
        if (cursor) cursor.visible = false
      }
    }

    function onMouseUp(e) {
      // Clique (sem drag) no step previewing seleciona um conector p/ edição
      if (step === 'previewing' && pinPickDownRef.current) {
        const d = Math.hypot(
          e.clientX - pinPickDownRef.current.x,
          e.clientY - pinPickDownRef.current.y,
        )
        pinPickDownRef.current = null
        if (d < 5) pickPinAt(e)
      }
      if (isPainting.current) {
        isPainting.current = false
        if (paintMode === 'brush' && brushBatchRef.current.size > 0) {
          // Consolida drag inteiro como uma entrada de undo
          paintHistRef.current.push([...brushBatchRef.current])
          brushBatchRef.current = new Set()
        } else if (paintMode === 'eraser') {
          // Borracha: limpa o batch (sem entrada de undo — usar Ctrl+Z não re-pinta)
          brushBatchRef.current = new Set()
        }
      }
    }

    function onContextMenu(e) { e.preventDefault() }

    canvas.addEventListener('mousedown', onMouseDown)
    canvas.addEventListener('mousemove', onMouseMove)
    canvas.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('contextmenu', onContextMenu)
    return () => {
      canvas.removeEventListener('mousedown', onMouseDown)
      canvas.removeEventListener('mousemove', onMouseMove)
      canvas.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('contextmenu', onContextMenu)
    }
  }, [step, paintMode, brushSize, fillAngle, sessionId, selectedPart])

  async function handlePaintClick(e) {
    const res = getRaycastFace(e)
    if (!res) return
    const { hit, meshIdx } = res
    const faceIdx = hit.faceIndex

    if (paintMode === 'brush' || paintMode === 'eraser') {
      const { brushSize: currentBrushSize, paintMode: currentMode } = useStore.getState()
      const faces = getFacesInRadius(hit, meshIdx, currentBrushSize)
      if (currentMode === 'eraser') {
        const painted = new Set(useStore.getState().paintedFaces)
        const toErase = faces.filter(f => painted.has(f))
        if (!toErase.length) return
        colorFaces(meshObjsRef.current[meshIdx].geometry, toErase, C.base)
        removePaintedFaces(toErase)
        return
      }
      paintHistRef.current.push(faces)
      colorFaces(meshObjsRef.current[meshIdx].geometry, faces, C.painted)
      addPaintedFaces(faces)
    } else if (paintMode === 'smart') {
      // Smart Select: servidor detecta região semântica por curvatura adaptativa
      useStore.getState().setLoading(true, t('detecting_region'), 30)
      try {
        const res2 = await api.smartSelect(sessionId, selectedPart, faceIdx)
        const faces = res2.face_indices
        paintHistRef.current.push(faces)
        colorFaces(meshObjsRef.current[meshIdx].geometry, faces, C.painted)
        addPaintedFaces(faces)
      } catch (err) {
        setError(err.message || t('err_smart'))
      } finally {
        useStore.getState().setLoading(false)
      }
    } else {
      // Flood fill (conta-gotas) — guard contra cliques concorrentes
      if (isProcessingFill.current) return
      isProcessingFill.current = true
      const point = toMeshSpace(hit.point, meshIdx)
      useStore.getState().setLoading(true, t('detecting_region'), 50)
      try {
        const data = meshDataRef.current[meshIdx]
        // Lazy-load adjacency data if not yet fetched
        if (!data?.face_adjacency) {
          const adj = await api.getMeshAdj(sessionId, selectedPart)
          data.face_adjacency = adj.face_adjacency
          data.face_adjacency_angles = adj.face_adjacency_angles
          if (meshObjsRef.current[meshIdx]?.geometry) {
            meshObjsRef.current[meshIdx].geometry._adjacency = adj.face_adjacency
            meshObjsRef.current[meshIdx].geometry._adjacencyAngles = adj.face_adjacency_angles
          }
        }
        const faceNormals = meshObjsRef.current[meshIdx]?.geometry?._faceNormals || null
        const { fillAngle: currentAngle, fillRadius: currentRadius } = useStore.getState()
        const angleRad = currentAngle * Math.PI / 180
        // 1. Flood fill por ângulo diedro (expande pela superfície suave)
        const rawFaces = floodFill(faceIdx, data.face_adjacency, data.face_adjacency_angles, angleRad, faceNormals)
        // 2. Filtro euclidiano: remove faces fora do raio 3D do clique
        const posArr = meshObjsRef.current[meshIdx].geometry.attributes.position.array
        const meshObj2 = meshObjsRef.current[meshIdx]
        const localHit = hit.point.clone().applyMatrix4(meshObj2.matrixWorld.clone().invert())
        const radiusFiltered = currentRadius > 0
          ? filterByRadiusPoint(rawFaces, posArr, localHit, currentRadius)
          : rawFaces
        // 3. Mantém o componente conectado ao clique (não o maior!)
        let faces = keepSeedComponent(new Set(radiusFiltered), data.face_adjacency, faceIdx)
        paintHistRef.current.push(faces)
        colorFaces(meshObjsRef.current[meshIdx].geometry, faces, C.painted)
        addPaintedFaces(faces)
      } catch (err) {
        setError(err.message || t('err_paint'))
      } finally {
        useStore.getState().setLoading(false)
        isProcessingFill.current = false
      }
    }
  }

  function handleBrushStroke(e) {
    const res = getRaycastFace(e)
    if (!res) return
    const { hit, meshIdx } = res
    const { brushSize: currentBrush, paintMode: currentMode } = useStore.getState()
    const faces = getFacesInRadius(hit, meshIdx, currentBrush)
    if (!faces.length) return

    if (currentMode === 'eraser') {
      const painted = new Set(useStore.getState().paintedFaces)
      const toErase = faces.filter(f => painted.has(f) && !brushBatchRef.current.has(f))
      if (!toErase.length) return
      colorFaces(meshObjsRef.current[meshIdx].geometry, toErase, C.base)
      toErase.forEach(f => brushBatchRef.current.add(f))
      removePaintedFaces(toErase)
      return
    }

    // Filtra só faces ainda não pintadas para não re-pintar
    const newFaces = faces.filter(f => !brushBatchRef.current.has(f))
    if (!newFaces.length) return
    colorFaces(meshObjsRef.current[meshIdx].geometry, newFaces, C.painted)
    newFaces.forEach(f => brushBatchRef.current.add(f))  // acumula no batch — push em mouseUp
    addPaintedFaces(newFaces)
  }

  // ── Controls: bloqueia só botão esquerdo em painting (direito/meio livre para orbit)
  useEffect(() => {
    if (!controlsRef.current) return
    controlsRef.current.blockLeftClick = (step === 'painting')

    // Pré-carrega adjacência ao entrar em painting para eliminar delay no 1º clique de conta-gotas
    if (step === 'painting' && sessionId && meshDataRef.current[0] && !meshDataRef.current[0].face_adjacency) {
      api.getMeshAdj(sessionId, useStore.getState().selectedPart).then(adj => {
        if (!meshDataRef.current[0]) return
        meshDataRef.current[0].face_adjacency = adj.face_adjacency
        meshDataRef.current[0].face_adjacency_angles = adj.face_adjacency_angles
      }).catch(() => {})
    }
  }, [step])

  // ── Grid toggle ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = showGrid
  }, [showGrid])

  // ── Wireframe toggle ──────────────────────────────────────────────────────
  function showWireframeMode(on) {
    for (const m of meshObjsRef.current) {
      if (m.material.wireframe !== undefined) m.material.wireframe = on
    }
  }

  useEffect(() => {
    showWireframeMode(showWireframe)
  }, [showWireframe])

  // ── X-Ray toggle (§2.3: inspecionar folga macho/fêmea) ───────────────────
  function showXrayMode(on) {
    for (const m of meshObjsRef.current) {
      m.material.transparent = on
      m.material.opacity = on ? 0.32 : 1.0
      m.material.depthWrite = !on
      m.material.needsUpdate = true
    }
  }

  useEffect(() => {
    showXrayMode(showXray)
  }, [showXray])

  // ── Joint preview pins ────────────────────────────────────────────────────
  function updatePinPreview() {
    const group = overlayGroupRef.current
    if (!group) return
    // Remove old (dispose para evitar memory leak na GPU)
    for (const p of pinPreviewRef.current) {
      group.remove(p)
      p.geometry.dispose()
      p.material.dispose()
    }
    pinPreviewRef.current = []

    const pins = useStore.getState().jointPins
    if (!pins?.length) return
    // No step result o overlay é controlado pelo toggle "Exibir encaixes"
    const visible = step === 'result' ? useStore.getState().showJoints : true
    const selectedIdx = useStore.getState().selectedPinIdx

    pins.forEach((pin, pinIdx) => {
      const [px, py, pz] = pin.position
      const dir = new THREE.Vector3(...pin.direction).normalize()
      const selected = pinIdx === selectedIdx
      const pinMat = new THREE.MeshPhongMaterial({
        color: C.pin, transparent: true, opacity: selected ? 0.95 : 0.7,
        emissive: selected ? new THREE.Color(0x2244aa) : new THREE.Color(0x000000),
      })

      const addMale = (geo, alongDir) => {
        const m = new THREE.Mesh(geo, pinMat)
        m.position.set(px, py, pz)
        m.position.addScaledVector(dir, alongDir)
        m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir)
        m.visible = visible
        m.userData.pinIdx = pinIdx
        group.add(m)
        pinPreviewRef.current.push(m)
      }

      // Macho (azul) — forma fiel ao joint_type (mesmas proporções do backend)
      const r = pin.pin_radius
      if (pin.joint_type === 'ball') {
        // Pescoço (70% do raio) + esfera na ponta
        const neckLen = Math.max(pin.depth - r, 0.5)
        addMale(new THREE.CylinderGeometry(r * 0.7, r * 0.7, neckLen, 16), neckLen / 2)
        addMale(new THREE.SphereGeometry(r, 20, 14), neckLen)
      } else if (pin.joint_type === 'dovetail') {
        // Tronco quadrado: base larga na face de corte, ponta a 65%
        const rBase = r * Math.SQRT2
        addMale(new THREE.CylinderGeometry(rBase * 0.65, rBase, pin.depth, 4), pin.depth / 2)
      } else {
        addMale(new THREE.CylinderGeometry(r, r, pin.depth, 16), pin.depth / 2)
      }

      // Hole indicator (red ring)
      const holeGeo = new THREE.TorusGeometry(pin.hole_radius, 0.5, 8, 16)
      const holeMat = new THREE.MeshPhongMaterial({ color: C.hole, transparent: true, opacity: 0.7 })
      const holeMesh = new THREE.Mesh(holeGeo, holeMat)
      holeMesh.position.set(px, py, pz)
      holeMesh.position.addScaledVector(dir, -pin.depth / 2)
      holeMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir)
      holeMesh.visible = visible
      holeMesh.userData.pinIdx = pinIdx
      group.add(holeMesh)
      pinPreviewRef.current.push(holeMesh)
    })
  }

  useEffect(() => {
    // Overlay dos pinos no preview E no resultado (controlado por showJoints)
    if (step === 'previewing' || step === 'result') updatePinPreview()
    else {
      const group = overlayGroupRef.current
      if (!group) return
      for (const p of pinPreviewRef.current) {
        group.remove(p)
        p.geometry.dispose()
        p.material.dispose()
      }
      pinPreviewRef.current = []
    }
  }, [step, jointPins, selectedPinIdx])

  // ── Joint visibility toggle ───────────────────────────────────────────────
  useEffect(() => {
    for (const p of pinPreviewRef.current) p.visible = showJoints
  }, [showJoints])

  // ── Cut plane gizmo (step = cutting) ─────────────────────────────────────
  const autoCutPlaneRef = useRef()

  useEffect(() => {
    const scene = sceneRef.current
    if (!scene) return

    const group = overlayGroupRef.current
    if (autoCutPlaneRef.current) { group.remove(autoCutPlaneRef.current); autoCutPlaneRef.current = null }
    if (step !== 'cutting' || !activeCutPlane) return

    const bounds = modelBounds || { min: [-100,-100,-100], max: [100,100,100] }
    const size = Math.max(
      bounds.max[0] - bounds.min[0],
      bounds.max[1] - bounds.min[1],
      bounds.max[2] - bounds.min[2],
    ) * 1.4

    const normal = new THREE.Vector3(
      activeCutPlane.axis === 'x' ? 1 : 0,
      activeCutPlane.axis === 'y' ? 1 : 0,
      activeCutPlane.axis === 'z' ? 1 : 0,
    )
    const origin = new THREE.Vector3(
      activeCutPlane.axis === 'x' ? activeCutPlane.position : (bounds.min[0] + bounds.max[0]) / 2,
      activeCutPlane.axis === 'y' ? activeCutPlane.position : (bounds.min[1] + bounds.max[1]) / 2,
      activeCutPlane.axis === 'z' ? activeCutPlane.position : (bounds.min[2] + bounds.max[2]) / 2,
    )

    // Plano principal (semi-transparente)
    const geo = new THREE.PlaneGeometry(size, size)
    const mat = new THREE.MeshBasicMaterial({
      color: C.cutPlane, side: THREE.DoubleSide, transparent: true, opacity: 0.18,
    })
    const plane = new THREE.Mesh(geo, mat)
    plane.position.copy(origin)
    plane.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal)

    // Borda (wireframe)
    const edgeGeo = new THREE.EdgesGeometry(geo)
    const edgeMat = new THREE.LineBasicMaterial({ color: C.cutPlane, opacity: 0.8, transparent: true })
    const edges = new THREE.LineSegments(edgeGeo, edgeMat)
    plane.add(edges)

    group.add(plane)
    autoCutPlaneRef.current = plane
  }, [step, activeCutPlane, modelBounds])

  // ── Cut plane visualization (após corte) ─────────────────────────────────
  useEffect(() => {
    const scene = sceneRef.current
    if (!scene) return
    const group = overlayGroupRef.current
    if (cutPlaneRef.current) { group.remove(cutPlaneRef.current); cutPlaneRef.current = null }
    if (!cutOrigin || !cutNormal || step === 'result') return

    const [ox, oy, oz] = cutOrigin
    const [nx, ny, nz] = cutNormal
    const normal = new THREE.Vector3(nx, ny, nz).normalize()

    const geo = new THREE.PlaneGeometry(100, 100)
    const mat = new THREE.MeshBasicMaterial({
      color: C.cutPlane, side: THREE.DoubleSide, transparent: true, opacity: 0.25
    })
    const plane = new THREE.Mesh(geo, mat)
    plane.position.set(ox, oy, oz)
    plane.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal)
    group.add(plane)
    cutPlaneRef.current = plane
  }, [cutOrigin, cutNormal, step])

  // ── Visibility: pane/tab filtering ───────────────────────────────────────
  const activeTab = useStore(s => s.activeTab)

  useEffect(() => {
    if (step !== 'result' || !meshObjsRef.current.length) return
    const { partAIdx, partBIdx } = useStore.getState()

    // paneIdx defined → side-by-side mode: each pane shows only its part
    // activeTab defined → tabs mode: show only active tab's part
    let onlyIdx = null
    if (paneIdx === 0) onlyIdx = partAIdx
    else if (paneIdx === 1) onlyIdx = partBIdx
    else if (paneIdx === undefined) {
      // single/tabs view: filter by activeTab
      const vm = useStore.getState().viewMode
      if (vm === 'tabs') onlyIdx = activeTab === 0 ? partAIdx : partBIdx
    }

    meshObjsRef.current.forEach((m, i) => {
      if (m) m.visible = (onlyIdx === null || i === onlyIdx)
    })

    // Re-fit camera to visible mesh only
    if (onlyIdx !== null) {
      setTimeout(fitView, 50)
    }
    // meshLoading nas deps: numa instância recém-montada (lado a lado/abas) as
    // malhas carregam DEPOIS do primeiro run — refiltra quando o load termina.
  }, [step, paneIdx, activeTab, meshLoading])

  // ── Fit view ──────────────────────────────────────────────────────────────
  function fitView() {
    if (!meshObjsRef.current.length) return
    const box = new THREE.Box3()
    for (const m of meshObjsRef.current) {
      m.updateMatrixWorld(true)
      box.expandByObject(m)
    }
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    const fov = camRef.current.fov * Math.PI / 180
    const dist = (maxDim / 2) / Math.tan(fov / 2) * 1.5

    const zDominant = size.z > size.y * 1.5
    const camY = zDominant ? dist * 0.8 : dist * 0.3
    controlsRef.current.reset(
      center.clone().add(new THREE.Vector3(dist * 0.4, camY, dist * 1.0)),
      center,
    )

    // Ajusta far clipping e fog para o tamanho real do modelo
    camRef.current.far = dist * 20
    camRef.current.updateProjectionMatrix()
    if (sceneRef.current?.fog) {
      // fog density: visível em ~3× maxDim, some suavemente depois
      sceneRef.current.fog.density = 0.8 / (dist * 3)
    }
  }

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  useEffect(() => {
    function onKey(e) {
      if (e.ctrlKey && e.key === 'z') undoPaint()
      if (e.key === 'f' || e.key === 'F') fitView()
      if (e.key === 'w' || e.key === 'W')
        useStore.setState(s => ({ showWireframe: !s.showWireframe }))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', display: 'block', cursor: step === 'painting' ? (paintMode === 'brush' ? 'crosshair' : paintMode === 'smart' ? 'cell' : 'pointer') : 'default' }}
      />
      {meshLoading && (
        <div className="mesh-loading-overlay">
          <div className="mesh-loading-ring" />
          <span className="mesh-loading-text">{loadProgress || t('loading_model')}</span>
          {loadProgress.includes('faces') && (
            <span className="mesh-loading-sub">{t('loading_large')}</span>
          )}
        </div>
      )}
    </div>
  )
})

export default Viewer3D
