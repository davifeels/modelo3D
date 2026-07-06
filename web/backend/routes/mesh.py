import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import io
import concurrent.futures
import numpy as np
import trimesh
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List

import session as sess
from src.importer import load_mesh, HEAVY_MESH_THRESHOLD

# Executor persistente — CRÍTICO: sem referência persistente o GC destrói o executor
# e bloqueia o thread principal esperando as tasks terminarem.
_bg_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="prebuild")
from src.segmentation import smart_segment, segment_multi, GRANULARITY_PRESETS
from src.cutter import (
    cut_mesh, split_by_components, region_grow_and_cut,
    get_cross_section_points, AXIS_NORMALS, cut_by_mask, cut_by_multi_mask,
)
from src.joints import (
    add_joints, JointParams, plan_pin_origins, boundary_perimeter, JOINT_TYPES,
    apply_joint_specs,
)

router = APIRouter(prefix="/api")


# ── Parâmetros automáticos de encaixe ────────────────────────────────────────

def auto_joint_params(
    mesh_a: trimesh.Trimesh,
    mesh_b: trimesh.Trimesh,
    cut_pts: np.ndarray,
    cut_normal: np.ndarray = None,
) -> JointParams:
    """Determina parâmetros de encaixe automaticamente pela geometria."""
    perimeter = 0.0
    if len(cut_pts) > 2 and cut_normal is not None:
        perimeter = boundary_perimeter(cut_pts, cut_normal)
    if perimeter <= 0.0:
        bb = np.vstack([mesh_a.bounds, mesh_b.bounds])
        diag = float(np.linalg.norm(bb[1::2].max(0) - bb[::2].min(0)))
        perimeter = diag * 2.5

    n_pins = max(1, min(6, int(perimeter / 30)))
    pin_radius = max(2.0, min(8.0, perimeter * 0.03))
    pin_depth = max(4.0, pin_radius * 2.5)

    return JointParams(
        pin_diameter=pin_radius * 2,
        pin_depth=pin_depth,
        tolerance=1.0,  # folga fixa 2mm (1mm por lado) — FDM padrão
        n_pins=n_pins,
    )


# ── Pydantic models ───────────────────────────────────────────────────────────

class RegionGrowReq(BaseModel):
    session_id: str
    part_idx: int = 0
    point: List[float]          # [x, y, z]
    angle_deg: float = 30.0

class CutReq(BaseModel):
    session_id: str
    part_idx: int = 0
    axis: str                   # x | y | z
    position: float

class SplitReq(BaseModel):
    session_id: str
    part_idx: int = 0

class PreviewJointsReq(BaseModel):
    session_id: str
    part_a_idx: int
    part_b_idx: int
    cut_origin: List[float]
    cut_normal: List[float]
    joint_type: Optional[str] = None    # "pin" | "ball" | "dovetail" (None = pin)
    fit: Optional[str] = None           # "flexivel" | "apertado" (None = flexivel)

class PinOverride(BaseModel):
    """Parâmetros individuais de UM conector (§2.2 — edição por conector)."""
    position: List[float]
    direction: Optional[List[float]] = None   # None = cut_normal
    joint_type: Optional[str] = None          # None = joint_type global do request
    diameter: Optional[float] = None          # mm; None = automático
    depth: Optional[float] = None             # mm; None = automático

class ConfirmReq(BaseModel):
    session_id: str
    part_a_idx: int
    part_b_idx: int
    cut_origin: List[float]
    cut_normal: List[float]
    joint_type: Optional[str] = None    # deve ser o mesmo usado no preview
    fit: Optional[str] = None           # deve ser o mesmo usado no preview
    pins: Optional[List[PinOverride]] = None  # None = planejamento automático

class PaintedCutReq(BaseModel):
    session_id: str
    part_idx: int = 0
    painted_face_indices: List[int]

class SuggestCutsReq(BaseModel):
    session_id: str
    part_idx: int = 0
    n_results: int = 5

class SmartSelectReq(BaseModel):
    session_id: str
    part_idx: int = 0
    face_idx: int           # face clicada pelo usuário
    max_region_pct: float = 0.6
    min_region_pct: float = 0.01


# ── Upload ────────────────────────────────────────────────────────────────────

_MAX_UPLOAD_MB = 200


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    import asyncio, tempfile
    allowed = {".stl", ".obj"}
    ext = os.path.splitext(file.filename)[1]
    if ext.lower() not in allowed:
        raise HTTPException(400, "Formato não suportado. Use STL ou OBJ.")

    # Limite de tamanho — sem ele um upload gigante derruba o processo por RAM
    max_bytes = _MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"Arquivo maior que {_MAX_UPLOAD_MB} MB.")

    # Salva em arquivo temporário para trimesh carregar
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        # Executa em thread pool com timeout de 60s para não travar indefinidamente
        loop = asyncio.get_running_loop()
        components, info = await asyncio.wait_for(
            loop.run_in_executor(None, load_mesh, tmp_path),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Tempo limite ao processar o arquivo.")
    except Exception as e:
        raise HTTPException(400, f"Arquivo inválido ou corrompido: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # load_mesh viu apenas o arquivo temporário — restaura o nome original do upload
    info["name"] = os.path.basename(file.filename)

    sid = sess.create()
    names = _make_names(info["name"], components)
    sess.update(sid, parts=components, names=names, info=info)

    # Pré-computa em background: binário de mesh + grafo de segmentação
    # IMPORTANTE: usa _bg_executor (referência módulo-nível) para evitar bloqueio por GC
    from src.segmentation import _build_csr as _seg_build_csr

    def _prebuild_cache():
        for i, p in enumerate(components):
            try:
                sess.mesh_to_binary(sid, i, p)
            except Exception:
                pass
            try:
                graph_cache = {'csr': _seg_build_csr(p)}
                s2 = sess.get(sid)
                # Só grava se a parte ainda é a mesma — um corte durante o
                # prebuild deslocaria os índices e o grafo iria para a parte errada
                if s2 and i < len(s2["parts"]) and s2["parts"][i] is p:
                    s2.setdefault(f"_seg_graph_{i}", {}).update(graph_cache)
            except Exception:
                pass

    _bg_executor.submit(_prebuild_cache)

    parts_meta = _parts_meta(components, names)

    d = info["dims_mm"]
    return {
        "session_id": sid,
        "is_heavy": info["is_heavy"],
        "info": {
            "name": info["name"],
            "vertices": info["vertices"],
            "faces": info["faces"],
            "dims": [float(d[0]), float(d[1]), float(d[2])],
            "is_watertight": info["is_watertight"],
            "was_repaired": info.get("was_repaired", False),
            "unit_hint": info["unit_hint"],
            "scaled_from": info.get("scaled_from"),
            "n_components": info["n_components"],
            "volume_cm3": info.get("volume_cm3"),
        },
        "parts": parts_meta,
    }


@router.get("/session/{session_id}")
def check_session(session_id: str):
    """Verifica se uma sessão ainda existe e retorna seus metadados."""
    s = sess.get(session_id)
    if not s or not s.get("parts"):
        raise HTTPException(404, "Sessão não encontrada ou expirada.")
    parts_meta = [
        {
            "idx": i,
            "name": s["names"][i] if "names" in s and i < len(s["names"]) else f"parte_{i}",
            "face_count": len(p.faces),
            "vertex_count": len(p.vertices),
            "is_watertight": bool(p.is_watertight),
            "bbox": p.bounds.tolist(),
            "dims": (p.bounds[1] - p.bounds[0]).tolist(),
        }
        for i, p in enumerate(s["parts"])
    ]
    raw_info = s.get("info", {})
    d = raw_info.get("dims_mm")
    info_out = {
        "name": raw_info.get("name", ""),
        "vertices": raw_info.get("vertices", 0),
        "faces": raw_info.get("faces", 0),
        "dims": d.tolist() if hasattr(d, "tolist") else (list(d) if d is not None else []),
        "is_watertight": raw_info.get("is_watertight", False),
        "unit_hint": raw_info.get("unit_hint", "mm"),
        "n_components": raw_info.get("n_components", len(s["parts"])),
        "volume_cm3": raw_info.get("volume_cm3"),
    }
    return {
        "session_id": session_id,
        "step": s.get("step", "loaded"),
        "parts": parts_meta,
        "info": info_out,
    }


@router.get("/mesh/{session_id}/{part_idx}")
def get_mesh(session_id: str, part_idx: int):
    """Retorna dados completos da mesh como JSON (fallback)."""
    s = _get_session(session_id)
    _check_idx(part_idx, s["parts"])
    mesh = s["parts"][part_idx]
    return sess.mesh_to_dict(mesh, s["names"][part_idx])


@router.get("/mesh-bin/{session_id}/{part_idx}")
def get_mesh_bin(session_id: str, part_idx: int):
    """Retorna mesh em formato binário compacto (muito mais rápido que JSON)."""
    s = _get_session(session_id)
    _check_idx(part_idx, s["parts"])
    mesh = s["parts"][part_idx]
    data = sess.mesh_to_binary(session_id, part_idx, mesh)
    return Response(content=data, media_type="application/octet-stream")


@router.get("/mesh-adj/{session_id}/{part_idx}")
def get_mesh_adj(session_id: str, part_idx: int):
    """Retorna apenas dados de adjacência com cache (lazy, para flood fill)."""
    s = _get_session(session_id)
    _check_idx(part_idx, s["parts"])
    mesh = s["parts"][part_idx]
    return sess.mesh_adjacency(session_id, part_idx, mesh)


@router.get("/mesh-stl/{session_id}/{part_idx}")
def get_mesh_stl(session_id: str, part_idx: int):
    """Retorna a mesh como STL binário para carregamento no Three.js."""
    s = _get_session(session_id)
    _check_idx(part_idx, s["parts"])
    mesh = s["parts"][part_idx]
    stl_bytes = mesh.export(file_type="stl")
    return Response(content=stl_bytes, media_type="application/octet-stream")


# ── Sugestão automática de planos de corte ───────────────────────────────────

@router.post("/suggest-cuts")
async def suggest_cuts(req: SuggestCutsReq):
    """Analisa o modelo e sugere os melhores planos de corte automaticamente."""
    import asyncio
    from src.segmentation import suggest_cut_planes

    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]

    def _run():
        return suggest_cut_planes(mesh, n_results=req.n_results)

    try:
        loop = asyncio.get_running_loop()
        suggestions = await asyncio.wait_for(
            loop.run_in_executor(None, _run),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Tempo limite ao analisar modelo.")
    except Exception as e:
        raise HTTPException(500, f"Erro na análise automática: {e}")

    bounds = mesh.bounds
    return {
        "suggestions": suggestions,
        "bounds": {
            "min": bounds[0].tolist(),
            "max": bounds[1].tolist(),
        },
    }


# ── Smart Select (segmentação automática por curvatura) ──────────────────────

@router.post("/smart-select")
async def smart_select(req: SmartSelectReq):
    """
    Detecta automaticamente a região semântica ao redor de uma face clicada.
    Roda em thread pool para não bloquear o event loop.
    """
    import asyncio
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]

    if req.face_idx < 0 or req.face_idx >= len(mesh.faces):
        raise HTTPException(422, f"face_idx inválido: {req.face_idx}")

    cache_key   = f"_seg_graph_{req.part_idx}"
    graph_cache = s.setdefault(cache_key, {})

    def _run():
        return smart_segment(
            mesh, req.face_idx,
            max_region_pct=req.max_region_pct,
            min_region_pct=req.min_region_pct,
            _graph_cache=graph_cache,
        )

    try:
        loop = asyncio.get_running_loop()
        face_indices = await loop.run_in_executor(None, _run)
    except Exception as e:
        raise HTTPException(500, f"Erro no smart select: {e}")

    total = len(mesh.faces)
    pct = len(face_indices) / total * 100

    return {
        "face_indices": [int(f) for f in face_indices],
        "count": len(face_indices),
        "total_faces": total,
        "coverage_pct": round(pct, 1),
    }


# ── Region growing (conta-gotas) ──────────────────────────────────────────────

@router.post("/region-grow")
def region_grow(req: RegionGrowReq):
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]
    base_name = s["names"][req.part_idx]
    point = np.array(req.point, dtype=float)

    try:
        part_painted, part_base, cut_origin, cut_normal = region_grow_and_cut(
            mesh, point, req.angle_deg
        )
    except Exception as e:
        raise HTTPException(422, str(e))

    total = len(part_painted.faces) + len(part_base.faces)
    pct = len(part_painted.faces) / total * 100

    # Briefing §2/§6: pintado = Parte B (vermelha, cavidades fêmeas);
    # não pintado = Parte A (azul, pinos machos). Parte A primeiro na lista.
    parts = list(s["parts"])
    names = list(s["names"])
    name_painted = f"{base_name}_pintado"
    name_base = f"{base_name}_base"
    parts[req.part_idx:req.part_idx + 1] = [part_base, part_painted]
    names[req.part_idx:req.part_idx + 1] = [name_base, name_painted]

    sess.update(req.session_id, parts=parts, names=names)
    _reassign_interfaces(req.session_id, s, base_name,
                         [name_base, name_painted], [part_base, part_painted])
    _register_interface(req.session_id, s, cut_origin, -cut_normal, name_base, name_painted)

    return {
        "cut_origin": cut_origin.tolist(),
        # Convenção dos encaixes: normal aponta de B (pintada) para A (base)
        "cut_normal": (-cut_normal).tolist(),
        "part_a_idx": req.part_idx,      # part_base = Parte A (azul, pinos)
        "part_b_idx": req.part_idx + 1,  # part_painted = Parte B (vermelha, cavidades)
        "paint_pct": round(pct, 1),
        "painted_faces": len(part_painted.faces),
        "base_faces": len(part_base.faces),
        "painted_watertight": bool(part_painted.is_watertight),
        "base_watertight": bool(part_base.is_watertight),
        "parts_meta": _parts_meta(parts, names),
    }


# ── Corte a partir de faces pintadas (pincel livre) ───────────────────────────

@router.post("/cut-from-painted")
def cut_from_painted(req: PaintedCutReq):
    """
    Separa a malha pela máscara de faces pintadas — SEM plano de corte.
    Parte B (vermelha, cavidades) = exatamente as faces pintadas;
    Parte A (azul, pinos) = todas as demais.
    cut_origin/cut_normal retornados são metadados da interface (encaixes).
    """
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]
    base_name = s["names"][req.part_idx]

    if not req.painted_face_indices:
        raise HTTPException(422, "Nenhuma face pintada.")

    grown_idx = np.array(req.painted_face_indices, dtype=np.int64)

    # Valida que os índices pertencem a esta parte (evita IndexError por sessão desatualizada)
    n_mesh_faces = len(mesh.faces)
    valid_mask = (grown_idx >= 0) & (grown_idx < n_mesh_faces)
    if not np.all(valid_mask):
        grown_idx = grown_idx[valid_mask]
    if len(grown_idx) == 0:
        raise HTTPException(422, "Nenhuma das faces pintadas pertence a esta parte. Recarregue o modelo.")

    try:
        part_painted, part_base, origin, normal = cut_by_mask(mesh, grown_idx)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(422, f"Erro ao separar a mesh: {e}")

    parts = list(s["parts"])
    names = list(s["names"])
    name_painted = f"{base_name}_pintado"
    name_base = f"{base_name}_base"
    # Briefing §2/§6: pintado = Parte B (vermelha, cavidades fêmeas);
    # não pintado = Parte A (azul, pinos machos). Parte A primeiro na lista.
    parts[req.part_idx:req.part_idx + 1] = [part_base, part_painted]
    names[req.part_idx:req.part_idx + 1] = [name_base, name_painted]
    sess.update(req.session_id, parts=parts, names=names)
    _reassign_interfaces(req.session_id, s, base_name,
                         [name_base, name_painted], [part_base, part_painted])
    _register_interface(req.session_id, s, origin, -normal, name_base, name_painted)

    total = len(part_painted.faces) + len(part_base.faces)
    return {
        "cut_origin": origin.tolist(),
        # cut_by_mask retorna normal base→pintada; encaixes usam B→A (pintada→base)
        "cut_normal": (-normal).tolist(),
        "part_a_idx": req.part_idx,      # part_base = Parte A (azul, pinos)
        "part_b_idx": req.part_idx + 1,  # part_painted = Parte B (vermelha, cavidades)
        "paint_pct": round(len(part_painted.faces) / total * 100, 1),
        "painted_watertight": bool(part_painted.is_watertight),
        "base_watertight": bool(part_base.is_watertight),
        "parts_meta": _parts_meta(parts, names),
    }


# ── Máscara multi-peça (§1 — modo Professional) ───────────────────────────────

class SegmentMaskReq(BaseModel):
    session_id: str
    part_idx: int = 0
    granularity: str = "media"      # "baixa" | "media" | "alta"

class MaskSplitReq(BaseModel):
    session_id: str
    part_idx: int = 0
    labels: List[int]
    region_id: int

class MultiMaskCutReq(BaseModel):
    session_id: str
    part_idx: int = 0
    labels: List[int]


@router.post("/segment-mask")
def segment_mask(req: SegmentMaskReq):
    """Gera a máscara de segmentação (labels por face) SEM cortar — revisão prévia."""
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]
    if req.granularity not in GRANULARITY_PRESETS:
        raise HTTPException(
            422, f"Granularidade inválida: {req.granularity!r}. Use {list(GRANULARITY_PRESETS)}."
        )
    graph_cache = s.setdefault(f"_seg_graph_{req.part_idx}", {})
    try:
        labels = segment_multi(mesh, req.granularity, _graph_cache=graph_cache)
    except Exception as e:
        raise HTTPException(500, f"Erro na segmentação: {e}")
    ids, sizes = np.unique(labels, return_counts=True)
    return {
        "labels": labels.tolist(),
        "n_regions": int(len(ids)),
        "region_sizes": {int(i): int(c) for i, c in zip(ids, sizes)},
    }


@router.post("/mask-split")
def mask_split(req: MaskSplitReq):
    """Ferramenta Split: subdivide UMA região da máscara em sub-regiões."""
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]
    labels = np.asarray(req.labels, dtype=np.int64)
    if len(labels) != len(mesh.faces):
        raise HTTPException(422, "labels não corresponde ao número de faces da parte.")
    region_faces = np.nonzero(labels == req.region_id)[0]
    if len(region_faces) == 0:
        raise HTTPException(422, f"Região {req.region_id} não existe na máscara.")

    sub = mesh.submesh([region_faces], append=True)
    # Guard: sem quebra REAL dentro da região (ex.: superfície curva lisa),
    # o Otsu degenera para o ruído de tesselação e estilhaça a região em
    # dezenas de fatias — rejeita antes de segmentar.
    ang = sub.face_adjacency_angles
    if len(ang) == 0 or float(np.degrees(ang.max())) < 20.0:
        raise HTTPException(422, "Não foi possível subdividir esta região (sem quebras internas).")
    try:
        sub_labels = segment_multi(sub, "alta")
    except Exception as e:
        raise HTTPException(500, f"Erro ao subdividir: {e}")
    if len(np.unique(sub_labels)) < 2:
        raise HTTPException(422, "Não foi possível subdividir esta região (sem quebras internas).")

    # sub-região 0 mantém o id original; as demais ganham ids novos
    new_labels = labels.copy()
    next_id = int(labels.max()) + 1
    for sub_id in np.unique(sub_labels):
        if sub_id == 0:
            continue
        new_labels[region_faces[sub_labels == sub_id]] = next_id
        next_id += 1
    ids, sizes = np.unique(new_labels, return_counts=True)
    return {
        "labels": new_labels.tolist(),
        "n_regions": int(len(ids)),
        "region_sizes": {int(i): int(c) for i, c in zip(ids, sizes)},
    }


@router.post("/cut-by-multi-mask")
def cut_by_multi_mask_route(req: MultiMaskCutReq):
    """
    Aplica a máscara: divide a parte em N peças fechadas e registra a
    interface de cada par adjacente (prontas para 'Add all connectors').
    """
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]
    base_name = s["names"][req.part_idx]
    labels = np.asarray(req.labels, dtype=np.int64)

    try:
        new_parts, interfaces = cut_by_multi_mask(mesh, labels)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao aplicar máscara: {e}")

    region_ids = [int(r) for r in np.unique(labels)]
    new_names = [f"{base_name}_r{str(i + 1).zfill(2)}" for i in range(len(new_parts))]
    name_by_region = dict(zip(region_ids, new_names))

    parts = list(s["parts"])
    names = list(s["names"])
    parts[req.part_idx:req.part_idx + 1] = new_parts
    names[req.part_idx:req.part_idx + 1] = new_names
    sess.update(req.session_id, parts=parts, names=names)
    # limpa cache de grafo da parte antiga (faces mudaram)
    s.pop(f"_seg_graph_{req.part_idx}", None)

    _reassign_interfaces(req.session_id, s, base_name, new_names, new_parts)
    for itf in interfaces:
        _register_interface(
            req.session_id, s, itf["origin"], itf["normal"],
            name_by_region[itf["region_a"]], name_by_region[itf["region_b"]],
        )

    return {
        "n_regions": len(new_parts),
        "n_interfaces": len(interfaces),
        "parts_meta": _parts_meta(parts, names),
    }


# ── Corte manual por plano ────────────────────────────────────────────────────

@router.post("/cut")
def cut(req: CutReq):
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]
    base_name = s["names"][req.part_idx]

    if req.axis not in ("x", "y", "z"):
        raise HTTPException(422, "Eixo inválido. Use x, y ou z.")

    try:
        part_a, part_b = cut_mesh(mesh, req.axis, req.position)
    except ValueError as e:
        raise HTTPException(422, str(e))

    normal = AXIS_NORMALS[req.axis].copy()
    origin = np.zeros(3)
    origin[{"x": 0, "y": 1, "z": 2}[req.axis]] = req.position
    cut_pts = get_cross_section_points(mesh, req.axis, req.position)

    parts = list(s["parts"])
    names = list(s["names"])
    na, nb = f"{base_name}_A", f"{base_name}_B"
    parts[req.part_idx:req.part_idx + 1] = [part_a, part_b]
    names[req.part_idx:req.part_idx + 1] = [na, nb]
    sess.update(req.session_id, parts=parts, names=names)
    _reassign_interfaces(req.session_id, s, base_name, [na, nb], [part_a, part_b])
    _register_interface(req.session_id, s, origin, normal, na, nb)

    return {
        "cut_origin": origin.tolist(),
        "cut_normal": normal.tolist(),
        "cut_pts": cut_pts.tolist(),
        "part_a_idx": req.part_idx,
        "part_b_idx": req.part_idx + 1,
        "parts_meta": _parts_meta(parts, names),
    }


# ── Separar componentes ───────────────────────────────────────────────────────

@router.post("/split-components")
def split_components(req: SplitReq):
    s = _get_session(req.session_id)
    _check_idx(req.part_idx, s["parts"])
    mesh = s["parts"][req.part_idx]
    base_name = s["names"][req.part_idx]

    components = split_by_components(mesh)
    if len(components) <= 1:
        return {"split": False, "parts_meta": _parts_meta(s["parts"], s["names"])}

    pad = len(str(len(components)))
    new_names = [f"{base_name}_parte_{str(i+1).zfill(pad)}" for i in range(len(components))]

    parts = list(s["parts"])
    names = list(s["names"])
    parts[req.part_idx:req.part_idx + 1] = components
    names[req.part_idx:req.part_idx + 1] = new_names
    sess.update(req.session_id, parts=parts, names=names)
    _reassign_interfaces(req.session_id, s, base_name, new_names, components)

    return {"split": True, "n_components": len(components), "parts_meta": _parts_meta(parts, names)}


# ── Preview de encaixes ───────────────────────────────────────────────────────

@router.post("/preview-joints")
def preview_joints(req: PreviewJointsReq):
    s = _get_session(req.session_id)
    _check_idx(req.part_a_idx, s["parts"])
    _check_idx(req.part_b_idx, s["parts"])

    mesh_a = s["parts"][req.part_a_idx]
    mesh_b = s["parts"][req.part_b_idx]
    cut_origin = np.array(req.cut_origin, dtype=float)
    cut_normal = np.array(req.cut_normal, dtype=float)
    norm_len = np.linalg.norm(cut_normal)
    if norm_len < 1e-9:
        raise HTTPException(422, "Normal do corte inválida (vetor zero).")
    cut_normal = cut_normal / norm_len
    cut_pts = _get_cut_pts(mesh_a, cut_origin, cut_normal, other=mesh_b)

    params = auto_joint_params(mesh_a, mesh_b, cut_pts, cut_normal)
    params.joint_type = _validate_joint_type(req.joint_type)
    fit = _validate_fit(req.fit)
    params.tolerance = JOINT_FITS[fit]
    origins, notes = plan_pin_origins(mesh_a, mesh_b, cut_pts, cut_normal, params)

    pins = []
    for o in origins:
        pins.append({
            "position": np.asarray(o, dtype=float).tolist(),
            "pin_radius": params.pin_diameter / 2,
            "hole_radius": params.pin_diameter / 2 + params.tolerance,
            "depth": params.pin_depth,
            "direction": cut_normal.tolist(),
            "joint_type": params.joint_type,
        })

    return {
        "pins": pins,
        "n_pins": len(origins),
        "joint_type": params.joint_type,
        "fit": fit,
        "pin_diameter": params.pin_diameter,
        "pin_depth": params.pin_depth,
        "tolerance": params.tolerance,
        "notes": notes,
    }


# ── Confirmar: adicionar encaixes reais ──────────────────────────────────────

@router.post("/confirm")
def confirm(req: ConfirmReq):
    s = _get_session(req.session_id)
    _check_idx(req.part_a_idx, s["parts"])
    _check_idx(req.part_b_idx, s["parts"])

    mesh_a = s["parts"][req.part_a_idx]
    mesh_b = s["parts"][req.part_b_idx]
    cut_origin = np.array(req.cut_origin, dtype=float)
    cut_normal = np.array(req.cut_normal, dtype=float)
    norm_len = np.linalg.norm(cut_normal)
    if norm_len < 1e-9:
        raise HTTPException(422, "Normal do corte inválida (vetor zero).")
    cut_normal = cut_normal / norm_len
    cut_pts = _get_cut_pts(mesh_a, cut_origin, cut_normal, other=mesh_b)

    params = auto_joint_params(mesh_a, mesh_b, cut_pts, cut_normal)
    params.joint_type = _validate_joint_type(req.joint_type)
    params.tolerance = JOINT_FITS[_validate_fit(req.fit)]

    if req.pins:
        # §2.2: cada conector com parâmetros próprios (editados no preview)
        specs = _pin_overrides_to_specs(req.pins, cut_normal, params)
        notes = []
        try:
            new_a, new_b, warnings = apply_joint_specs(mesh_a, mesh_b, specs)
        except Exception as e:
            raise HTTPException(500, f"Erro ao gerar encaixes: {e}")
    else:
        # Mesmo planejamento do preview — o usuário confirma o que viu
        origins, notes = plan_pin_origins(mesh_a, mesh_b, cut_pts, cut_normal, params)
        try:
            new_a, new_b, warnings = add_joints(
                mesh_a, mesh_b, cut_origin, cut_normal, params, cut_pts,
                origins=origins,
            )
        except Exception as e:
            raise HTTPException(500, f"Erro ao gerar encaixes: {e}")
    warnings = notes + warnings

    parts = list(s["parts"])
    parts[req.part_a_idx] = new_a
    parts[req.part_b_idx] = new_b
    sess.update(req.session_id, parts=parts)
    _mark_interface_done(req.session_id, s,
                         s["names"][req.part_a_idx], s["names"][req.part_b_idx])

    return {
        "warnings": warnings,
        "parts_meta": _parts_meta(parts, s["names"]),
    }


# ── Multi-interface: Add all connectors (§2.3) ───────────────────────────────

@router.get("/interfaces/{sid}")
def list_interfaces(sid: str):
    """Interfaces de corte pendentes (sem conector) da sessão."""
    s = _get_session(sid)
    pending = _pending_interfaces(s)
    return {"pending": pending, "n_pending": len(pending)}


class ConfirmAllReq(BaseModel):
    session_id: str
    joint_type: Optional[str] = None
    fit: Optional[str] = None


@router.post("/confirm-all")
def confirm_all(req: ConfirmAllReq):
    """Gera conectores default em TODAS as interfaces de corte pendentes."""
    s = _get_session(req.session_id)
    jt = _validate_joint_type(req.joint_type)
    tol = JOINT_FITS[_validate_fit(req.fit)]
    pending = _pending_interfaces(s)
    if not pending:
        return {"n_processed": 0, "warnings": [],
                "parts_meta": _parts_meta(s["parts"], s["names"])}

    parts = list(s["parts"])
    all_warnings = []
    n_done = 0
    for itf in pending:
        ia, ib = itf["part_a_idx"], itf["part_b_idx"]
        mesh_a, mesh_b = parts[ia], parts[ib]
        origin = np.array(itf["origin"], dtype=float)
        normal = np.array(itf["normal"], dtype=float)
        prefix = f"{itf['name_a']} ↔ {itf['name_b']}: "
        try:
            cut_pts = _get_cut_pts(mesh_a, origin, normal, other=mesh_b)
            params = auto_joint_params(mesh_a, mesh_b, cut_pts, normal)
            params.joint_type = jt
            params.tolerance = tol
            origins, notes = plan_pin_origins(mesh_a, mesh_b, cut_pts, normal, params)
            new_a, new_b, warns = add_joints(
                mesh_a, mesh_b, origin, normal, params, cut_pts, origins=origins,
            )
            parts[ia], parts[ib] = new_a, new_b
            n_done += 1
            all_warnings += [prefix + w for w in (notes + warns)]
            _mark_interface_done(req.session_id, s, itf["name_a"], itf["name_b"])
        except Exception as e:
            all_warnings.append(prefix + f"falhou — {e}")

    sess.update(req.session_id, parts=parts)
    return {
        "n_processed": n_done,
        "warnings": all_warnings,
        "parts_meta": _parts_meta(parts, s["names"]),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(sid: str) -> dict:
    s = sess.get(sid)
    if not s:
        raise HTTPException(404, "Sessão não encontrada ou expirada.")
    return s


def _check_idx(idx: int, lst: list):
    if idx < 0 or idx >= len(lst):
        raise HTTPException(422, f"Índice de parte inválido: {idx}")


def _validate_joint_type(joint_type: Optional[str]) -> str:
    if joint_type is None:
        return "pin"
    if joint_type not in JOINT_TYPES:
        raise HTTPException(
            422, f"Tipo de conector inválido: {joint_type!r}. Use um de {list(JOINT_TYPES)}."
        )
    return joint_type


# Assembly Fit — tolerância por lado (mm). Flexível = padrão FDM atual;
# apertado = encaixe justo (mesmo valor do config joint.tolerance_mm).
JOINT_FITS = {"flexivel": 1.0, "apertado": 0.2}


def _validate_fit(fit: Optional[str]) -> str:
    if fit is None:
        return "flexivel"
    if fit not in JOINT_FITS:
        raise HTTPException(
            422, f"Fit inválido: {fit!r}. Use um de {list(JOINT_FITS)}."
        )
    return fit


_MAX_PINS_PER_CUT = 12


def _register_interface(sid: str, s: dict, origin, normal, name_a: str, name_b: str):
    """
    Registra uma interface de corte na sessão (§2.3 — 'Add all connectors').
    Partes são referenciadas por NOME: índices deslocam a cada novo corte.
    """
    interfaces = list(s.get("interfaces", []))
    interfaces.append({
        "origin": np.asarray(origin, dtype=float).tolist(),
        "normal": np.asarray(normal, dtype=float).tolist(),
        "name_a": name_a,
        "name_b": name_b,
        "done": False,
    })
    sess.update(sid, interfaces=interfaces)


def _mark_interface_done(sid: str, s: dict, name_a: str, name_b: str):
    interfaces = list(s.get("interfaces", []))
    for itf in interfaces:
        if not itf["done"] and {itf["name_a"], itf["name_b"]} == {name_a, name_b}:
            itf["done"] = True
            break
    sess.update(sid, interfaces=interfaces)


def _pending_interfaces(s: dict) -> list:
    """Interfaces não processadas cujas partes ainda existem (por nome)."""
    names = s["names"]
    result = []
    for itf in s.get("interfaces", []):
        if itf["done"]:
            continue
        if itf["name_a"] not in names or itf["name_b"] not in names:
            continue  # parte sumiu e não foi reatribuída — interface obsoleta
        result.append({
            **itf,
            "part_a_idx": names.index(itf["name_a"]),
            "part_b_idx": names.index(itf["name_b"]),
        })
    return result


def _reassign_interfaces(sid: str, s: dict, old_name: str,
                         child_names: list, child_meshes: list):
    """
    Uma parte com interface pendente foi recortada: a interface antiga ainda
    existe fisicamente — migra a referência para o filho mais próximo da
    origem daquela interface.
    """
    interfaces = list(s.get("interfaces", []))
    changed = False
    for itf in interfaces:
        if itf["done"] or old_name not in (itf["name_a"], itf["name_b"]):
            continue
        origin = np.array(itf["origin"], dtype=float)[None, :]
        best_name, best_d = None, float("inf")
        for name, mesh in zip(child_names, child_meshes):
            try:
                d = float(mesh.nearest.on_surface(origin)[1][0])
            except Exception:
                d = float(np.linalg.norm(mesh.centroid - origin[0]))
            if d < best_d:
                best_name, best_d = name, d
        key = "name_a" if itf["name_a"] == old_name else "name_b"
        itf[key] = best_name
        changed = True
    if changed:
        sess.update(sid, interfaces=interfaces)


def _pin_overrides_to_specs(pins, cut_normal: np.ndarray, base: JointParams) -> list:
    """Converte PinOverride[] em specs (origin, direction, JointParams) p/ apply_joint_specs."""
    if len(pins) > _MAX_PINS_PER_CUT:
        raise HTTPException(422, f"Máximo de {_MAX_PINS_PER_CUT} conectores por corte.")
    specs = []
    for i, po in enumerate(pins):
        if len(po.position) != 3:
            raise HTTPException(422, f"Conector {i+1}: position deve ter 3 componentes.")
        jt = _validate_joint_type(po.joint_type) if po.joint_type else base.joint_type
        diameter = po.diameter if po.diameter is not None else base.pin_diameter
        depth = po.depth if po.depth is not None else base.pin_depth
        if diameter <= 0 or depth <= 0:
            raise HTTPException(422, f"Conector {i+1}: diâmetro e profundidade devem ser > 0.")
        if po.direction is not None:
            direction = np.array(po.direction, dtype=float)
            if len(po.direction) != 3 or np.linalg.norm(direction) < 1e-9:
                raise HTTPException(422, f"Conector {i+1}: direção inválida.")
        else:
            direction = cut_normal
        p = JointParams(
            pin_diameter=diameter, pin_depth=depth,
            tolerance=base.tolerance, n_pins=1, joint_type=jt,
        )
        specs.append((np.array(po.position, dtype=float), direction, p))
    return specs


def _make_names(filename: str, parts: list) -> list:
    base = filename.rsplit(".", 1)[0]
    if len(parts) == 1:
        return [base]
    pad = len(str(len(parts)))
    return [f"{base}_parte_{str(i+1).zfill(pad)}" for i in range(len(parts))]


def _parts_meta(parts, names):
    result = []
    for i, p in enumerate(parts):
        bounds = p.bounds  # None se mesh vazia
        if bounds is not None:
            bbox = {"min": bounds[0].tolist(), "max": bounds[1].tolist()}
            dims = (bounds[1] - bounds[0]).tolist()
        else:
            bbox = {"min": [0,0,0], "max": [0,0,0]}
            dims = [0,0,0]
        result.append({
            "idx": i,
            "name": names[i] if i < len(names) else f"parte_{i}",
            "face_count": len(p.faces),
            "vertex_count": len(p.vertices),
            "watertight": bool(p.is_watertight),
            "bbox": bbox,
            "dims": dims,
        })
    return result


def _get_cut_pts(mesh: trimesh.Trimesh, origin: np.ndarray,
                 normal: np.ndarray = None,
                 other: trimesh.Trimesh = None) -> np.ndarray:
    """
    Pontos da borda de corte entre as duas partes.
    Preferência: costura real (vértices compartilhados entre as partes) —
    funciona para corte por máscara E por plano. Fallback: interseção por
    plano; por último, o próprio origin.
    """
    if normal is None:
        normal = np.array([0., 0., 1.])

    if other is not None and len(mesh.vertices) and len(other.vertices):
        try:
            from scipy.spatial import cKDTree
            va = np.asarray(mesh.vertices, dtype=float)
            vb = np.asarray(other.vertices, dtype=float)
            # Subamostra para não explodir em malhas gigantes
            step = max(1, len(va) // 20000)
            sample = va[::step]
            dists, _ = cKDTree(vb).query(sample, distance_upper_bound=1e-3)
            seam = sample[np.isfinite(dists)]
            if len(seam) >= 3:
                return seam
        except Exception:
            pass

    try:
        lines = trimesh.intersections.mesh_plane(mesh, normal, origin)
        if lines is not None and len(lines) > 0:
            return np.array(lines).reshape(-1, 3)
    except Exception:
        pass
    return np.array([origin])
