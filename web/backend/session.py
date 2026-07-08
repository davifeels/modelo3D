import uuid
import time
import struct
import threading
import trimesh
import numpy as np
from typing import Optional

_SESSION_TTL = 3600  # 1 hora

_store: dict = {}
_lock = threading.Lock()


def _cleanup():
    """Remove sessões expiradas."""
    while True:
        time.sleep(300)
        now = time.time()
        with _lock:
            expired = [k for k, v in _store.items() if now - v["last_access"] > _SESSION_TTL]
            for k in expired:
                del _store[k]


threading.Thread(target=_cleanup, daemon=True).start()


def create(owner: Optional[str] = None) -> str:
    sid = str(uuid.uuid4())
    with _lock:
        _store[sid] = {
            "owner": owner,     # user.id dono da sessão (isolamento entre contas)
            "parts": [],
            "names": [],
            "info": {},
            "joint_info": {},
            "_bin_cache": {},   # part_idx -> bytes (invalidado no update)
            "_adj_cache": {},   # part_idx -> dict
            "last_access": time.time(),
        }
    return sid


def get(sid: str) -> Optional[dict]:
    with _lock:
        s = _store.get(sid)
        if s:
            s["last_access"] = time.time()
        return s


def owned_by(sid: str, user_id: str) -> bool:
    """False se a sessão existe e pertence a OUTRO usuário. Sessões sem dono
    (legado) passam — o vínculo é defesa em profundidade sobre o UUID."""
    with _lock:
        s = _store.get(sid)
        if not s:
            return True  # inexistência é tratada como 404 pelos handlers
        owner = s.get("owner")
        return owner is None or owner == user_id


def update(sid: str, **kwargs):
    with _lock:
        s = _store.get(sid)
        if s:
            s.update(kwargs)
            # Partes mudaram → invalida caches de geometria
            if "parts" in kwargs:
                s["_bin_cache"] = {}
                s["_adj_cache"] = {}
                # Grafos de segmentação são indexados por part_idx — índices
                # deslocam a cada corte; um grafo antigo em índice novo gera
                # labels/regiões de OUTRA malha.
                for k in [k for k in s if isinstance(k, str) and k.startswith("_seg_graph_")]:
                    del s[k]
            s["last_access"] = time.time()


def delete(sid: str):
    with _lock:
        _store.pop(sid, None)


# ── Formato binário compacto ──────────────────────────────────────────────────
#
# Layout (little-endian):
#   [u32 nVerts] [u32 nFaces]
#   [float32 * nVerts * 3]  ← vertices
#   [u32 * nFaces * 3]      ← faces
#   [float32 * nVerts * 3]  ← vertex normals
#   [float32 * 3]           ← centroid
#   [float32 * 3]           ← bbox_min
#   [float32 * 3]           ← bbox_max
#   [u8 is_watertight]      ← 1 ou 0
#   [float32 volume_cm3]    ← 0.0 se não watertight
#
# Total para 100k faces / 50k verts ≈ 2.4 MB binário vs ~15 MB JSON

def mesh_to_binary(sid: str, part_idx: int, mesh: trimesh.Trimesh) -> bytes:
    """Serializa trimesh para binário compacto com cache por sessão."""
    with _lock:
        s = _store.get(sid)
        if s and part_idx in s.get("_bin_cache", {}):
            return s["_bin_cache"][part_idx]

    v = np.asarray(mesh.vertices, dtype=np.float32) if len(mesh.vertices) else np.zeros((0,3), np.float32)
    f = np.asarray(mesh.faces, dtype=np.uint32) if len(mesh.faces) else np.zeros((0,3), np.uint32)
    mesh.vertex_normals  # força cálculo
    n = np.asarray(mesh.vertex_normals, dtype=np.float32) if len(mesh.vertices) else np.zeros((0,3), np.float32)
    bb = mesh.bounds.astype(np.float32) if mesh.bounds is not None else np.zeros((2,3), np.float32)
    center = np.asarray(mesh.centroid, dtype=np.float32) if len(mesh.vertices) else np.zeros(3, np.float32)

    is_wt = bool(mesh.is_watertight)
    vol = 0.0
    if is_wt:
        try:
            vol = float(mesh.volume) / 1000.0
        except Exception:
            pass

    header = struct.pack('<II', len(v), len(f))
    data = (
        header
        + v.tobytes()
        + f.tobytes()
        + n.tobytes()
        + center.tobytes()
        + bb[0].tobytes()
        + bb[1].tobytes()
        + struct.pack('<Bf', 1 if is_wt else 0, vol)
    )

    with _lock:
        s = _store.get(sid)
        if s:
            parts = s.get("parts") or []
            # Só grava se a mesh ainda é a parte atual naquele índice — o
            # prebuild em background pode terminar DEPOIS de um corte e
            # gravaria a geometria antiga para a parte nova.
            if part_idx < len(parts) and parts[part_idx] is mesh:
                s["_bin_cache"][part_idx] = data

    return data


def mesh_adjacency(sid: str, part_idx: int, mesh: trimesh.Trimesh) -> dict:
    """Dados de adjacência com cache por sessão (só usados no flood fill)."""
    with _lock:
        s = _store.get(sid)
        if s and part_idx in s.get("_adj_cache", {}):
            return s["_adj_cache"][part_idx]

    result = {
        "face_adjacency": mesh.face_adjacency.tolist(),
        "face_adjacency_angles": mesh.face_adjacency_angles.tolist(),
    }

    with _lock:
        s = _store.get(sid)
        if s:
            parts = s.get("parts") or []
            if part_idx < len(parts) and parts[part_idx] is mesh:
                s["_adj_cache"][part_idx] = result

    return result


def mesh_to_dict(mesh: trimesh.Trimesh, name: str) -> dict:
    """Fallback JSON (mantido para compatibilidade)."""
    v = np.asarray(mesh.vertices, dtype=np.float32)
    f = np.asarray(mesh.faces, dtype=np.int32)
    mesh.vertex_normals
    n = np.asarray(mesh.vertex_normals, dtype=np.float32)
    bb = mesh.bounds
    vol = None
    if mesh.is_watertight:
        try:
            vol = float(mesh.volume) / 1000.0
        except Exception:
            pass
    if bb is not None:
        bbox = {"min": bb[0].tolist(), "max": bb[1].tolist()}
        dims = (bb[1] - bb[0]).tolist()
        center = mesh.centroid.tolist()
    else:
        bbox = {"min": [0,0,0], "max": [0,0,0]}
        dims = [0,0,0]
        center = [0,0,0]
    return {
        "name": name,
        "vertices": v.flatten().tolist(),
        "faces": f.flatten().tolist(),
        "normals": n.flatten().tolist(),
        "face_count": int(len(f)),
        "vertex_count": int(len(v)),
        "is_watertight": bool(mesh.is_watertight),
        "volume_cm3": vol,
        "bbox": bbox,
        "dims": dims,
        "center": center,
    }
