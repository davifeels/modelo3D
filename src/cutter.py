import trimesh
import numpy as np

AXIS_NORMALS = {
    "x": np.array([1.0, 0.0, 0.0]),
    "y": np.array([0.0, 1.0, 0.0]),
    "z": np.array([0.0, 0.0, 1.0]),
}
AXIS_IDX = {"x": 0, "y": 1, "z": 2}


def cut_mesh(mesh: trimesh.Trimesh, axis: str, position: float):
    """Corta a mesh no eixo/posição. Retorna (parte_positiva, parte_negativa)."""
    normal = AXIS_NORMALS[axis].copy()
    origin = np.zeros(3)
    origin[AXIS_IDX[axis]] = position

    part_pos = trimesh.intersections.slice_mesh_plane(mesh, normal, origin, cap=True)
    part_neg = trimesh.intersections.slice_mesh_plane(mesh, -normal, origin, cap=True)

    if part_pos is None or len(part_pos.faces) == 0:
        raise ValueError("Corte gerou parte vazia no lado positivo. Tente outra posição.")
    if part_neg is None or len(part_neg.faces) == 0:
        raise ValueError("Corte gerou parte vazia no lado negativo. Tente outra posição.")

    return part_pos, part_neg


def get_cross_section_centroid(mesh: trimesh.Trimesh, axis: str, position: float) -> np.ndarray:
    """Retorna o centróide da seção transversal no plano de corte."""
    normal = AXIS_NORMALS[axis].copy()
    origin = np.zeros(3)
    origin[AXIS_IDX[axis]] = position

    try:
        lines = trimesh.intersections.mesh_plane(mesh, normal, origin)
        if lines is not None and len(lines) > 0:
            pts = np.array(lines).reshape(-1, 3)
            return pts.mean(axis=0)
    except Exception:
        pass

    c = mesh.centroid.copy()
    c[AXIS_IDX[axis]] = position
    return c


def get_cross_section_points(mesh: trimesh.Trimesh, axis: str, position: float) -> np.ndarray:
    """Retorna todos os pontos da seção transversal, ou centróide como fallback."""
    normal = AXIS_NORMALS[axis].copy()
    origin = np.zeros(3)
    origin[AXIS_IDX[axis]] = position

    try:
        lines = trimesh.intersections.mesh_plane(mesh, normal, origin)
        if lines is not None and len(lines) > 0:
            return np.array(lines).reshape(-1, 3)
    except Exception:
        pass

    return np.array([get_cross_section_centroid(mesh, axis, position)])


def split_by_components(mesh: trimesh.Trimesh) -> list:
    """
    Divide a mesh nos seus componentes conectados.
    Retorna lista ordenada por número de faces (maior primeiro).
    Fragmentos com menos de 4 faces são descartados.
    """
    parts = mesh.split(only_watertight=False)
    if isinstance(parts, trimesh.Trimesh):
        return [parts]

    significant = [p for p in parts if len(p.faces) >= 4]
    if not significant:
        return [mesh]

    significant.sort(key=lambda p: len(p.faces), reverse=True)
    return significant


def simplify_mesh(mesh: trimesh.Trimesh, target_faces: int) -> trimesh.Trimesh:
    """
    Simplifica a mesh para o número alvo de faces usando decimação via PyVista/VTK.
    Retorna a mesh original se a simplificação falhar ou não for necessária.
    """
    if len(mesh.faces) <= target_faces:
        return mesh

    try:
        import pyvista as pv

        verts = np.asarray(mesh.vertices, dtype=float)
        faces_arr = np.asarray(mesh.faces, dtype=np.int32)
        faces_pv = np.hstack(
            [np.full((len(faces_arr), 1), 3, dtype=np.int32), faces_arr]
        ).ravel()
        pv_mesh = pv.PolyData(verts, faces_pv)

        reduction = 1.0 - (target_faces / len(mesh.faces))
        reduction = max(0.01, min(0.99, reduction))

        decimated = pv_mesh.decimate(reduction)

        raw = decimated.faces
        if len(raw) == 0:
            return mesh
        tri_faces = raw.reshape(-1, 4)[:, 1:]
        result = trimesh.Trimesh(
            vertices=decimated.points, faces=tri_faces, process=False
        )
        return result

    except Exception:
        return mesh


# ── Pintura automática (região growing) ──────────────────────────────────────

def _close_open_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Fecha buracos abertos numa mesh usando PyVista/VTK.
    Tenta trimesh primeiro (rápido), depois PyVista (mais robusto para buracos grandes).
    """
    # Tentativa 1: trimesh repair (funciona bem para buracos pequenos)
    try:
        trimesh.repair.fill_holes(mesh)
        if mesh.is_watertight:
            return mesh
    except Exception:
        pass

    # Tentativa 2: PyVista fill_holes (funciona para buracos grandes e complexos)
    try:
        import pyvista as pv
        verts = np.asarray(mesh.vertices, dtype=float)
        faces_arr = np.asarray(mesh.faces, dtype=np.int32)
        faces_pv = np.hstack(
            [np.full((len(faces_arr), 1), 3, dtype=np.int32), faces_arr]
        ).ravel()
        pv_mesh = pv.PolyData(verts, faces_pv)
        # hole_size: perímetro máximo dos buracos a fechar (valor grande = fecha tudo)
        filled = pv_mesh.fill_holes(hole_size=1_000_000)
        raw = filled.faces
        if len(raw) == 0:
            return mesh
        tri_faces = raw.reshape(-1, 4)[:, 1:]
        closed = trimesh.Trimesh(
            vertices=filled.points, faces=tri_faces, process=False
        )
        closed.process(validate=False)
        return closed
    except Exception:
        pass

    mesh.process(validate=False)
    return mesh


def _bfs_region(mesh: trimesh.Trimesh, start_face: int, angle_deg: float):
    """BFS region growing. Retorna (grown_idx_array, rest_idx_array, ratio)."""
    n_faces = len(mesh.faces)
    threshold = np.radians(angle_deg)

    adj_pairs = mesh.face_adjacency
    adj_angles = mesh.face_adjacency_angles

    neighbors = [[] for _ in range(n_faces)]
    for (f1, f2), ang in zip(adj_pairs, adj_angles):
        if ang < threshold:
            neighbors[f1].append(f2)
            neighbors[f2].append(f1)

    visited = set()
    stack = [start_face]
    while stack:
        face = stack.pop()
        if face in visited:
            continue
        visited.add(face)
        for nb in neighbors[face]:
            if nb not in visited:
                stack.append(nb)

    grown_idx = np.array(sorted(visited), dtype=np.int64)
    all_idx = np.arange(n_faces, dtype=np.int64)
    rest_idx = np.setdiff1d(all_idx, grown_idx)
    ratio = len(grown_idx) / n_faces
    return grown_idx, rest_idx, ratio


def _boundary_plane(mesh: trimesh.Trimesh, grown_idx: np.ndarray) -> tuple:
    """
    Encontra o plano médio entre a região crescida e o resto.
    Usa PCA nos vértices da fronteira.
    Retorna (origin, normal).
    """
    grown_set = set(grown_idx.tolist())
    adj = mesh.face_adjacency
    all_faces = np.asarray(mesh.faces)

    # Vértices compartilhados entre faces grown e not-grown
    boundary_verts = set()
    for f1, f2 in adj:
        in1 = f1 in grown_set
        in2 = f2 in grown_set
        if in1 != in2:
            shared = set(all_faces[f1].tolist()) & set(all_faces[f2].tolist())
            boundary_verts.update(shared)

    if len(boundary_verts) < 3:
        return mesh.centroid.copy(), np.array([0., 0., 1.])

    pts = np.asarray(mesh.vertices)[list(boundary_verts)]
    center = pts.mean(axis=0)
    cov = np.cov((pts - center).T)
    _, evecs = np.linalg.eigh(cov)
    # Menor autovetor = direção de menor variância = normal do plano
    normal = evecs[:, 0]
    normal = normal / np.linalg.norm(normal)
    return center, normal


def region_grow_and_cut(
    mesh: trimesh.Trimesh,
    point: np.ndarray,
    angle_deg: float = 30.0,
) -> tuple:
    """
    "Varinha mágica" 3D com corte limpo:
    1. Detecta a região pelo ângulo diedro (region growing)
    2. Determina o plano médio da fronteira via PCA
    3. Realiza um corte PLANAR nesse plano (garante malhas fechadas + watertight)

    Retorna (parte_pintada, parte_base, origin, normal).
    Lança ValueError se a região for trivial ou o corte falhar.
    """
    verts = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=np.int64)

    # Vértice mais próximo do clique → face de partida
    dists_v = np.linalg.norm(verts - point, axis=1)
    closest_vert = int(np.argmin(dists_v))
    mask = np.any(faces == closest_vert, axis=1)
    candidate_faces = np.where(mask)[0]
    if len(candidate_faces) == 0:
        raise ValueError("Nenhuma face encontrada próxima ao ponto clicado.")
    start_face = int(candidate_faces[0])

    grown_idx, rest_idx, ratio = _bfs_region(mesh, start_face, angle_deg)

    if ratio > 0.97:
        raise ValueError(
            f"Região cresceu para {ratio*100:.0f}% da mesh. "
            "Reduza o ângulo de limite."
        )
    if ratio < 0.003:
        raise ValueError(
            "Região muito pequena (< 0.3%). "
            "Aumente o ângulo de limite."
        )

    # Plano de corte via PCA na fronteira
    origin, normal = _boundary_plane(mesh, grown_idx)

    # Decide qual lado é "painted" (o lado que contém o centroide da região grown)
    grown_centroid = np.asarray(mesh.vertices)[grown_idx].mean(axis=0)
    sign = np.dot(grown_centroid - origin, normal)
    if sign < 0:
        normal = -normal

    # Corte planar limpo (cap=True → malhas fechadas)
    part_painted = trimesh.intersections.slice_mesh_plane(mesh, normal, origin, cap=True)
    part_base = trimesh.intersections.slice_mesh_plane(mesh, -normal, origin, cap=True)

    if part_painted is None or len(part_painted.faces) == 0:
        raise ValueError("Corte gerou parte pintada vazia. Tente outro ponto ou ângulo.")
    if part_base is None or len(part_base.faces) == 0:
        raise ValueError("Corte gerou base vazia. Tente outro ponto ou ângulo.")

    return part_painted, part_base, origin, normal


# ── Auto-detecção de interface para encaixe ───────────────────────────────────

def find_interface(
    mesh_a: trimesh.Trimesh,
    mesh_b: trimesh.Trimesh,
) -> tuple:
    """
    Detecta a interface entre dois meshes (onde eles se tocam / ficam próximos).
    Retorna (origin, normal) para posicionamento do encaixe.
    """
    from scipy.spatial import cKDTree

    verts_a = np.asarray(mesh_a.vertices, dtype=float)
    verts_b = np.asarray(mesh_b.vertices, dtype=float)

    # Subsample para performance (máx 3000 vértices por mesh)
    step_a = max(1, len(verts_a) // 3000)
    step_b = max(1, len(verts_b) // 3000)
    sa = verts_a[::step_a]
    sb = verts_b[::step_b]

    tree_b = cKDTree(sb)
    dists, _ = tree_b.query(sa)

    # Os 10% mais próximos = região de fronteira
    thresh = np.percentile(dists, 10)
    thresh = max(thresh, 0.5)
    boundary_pts = sa[dists <= thresh]

    if len(boundary_pts) == 0:
        boundary_pts = sa[[int(np.argmin(dists))]]

    origin = boundary_pts.mean(axis=0)

    # Normal = direção do centroide de B para A (pino aponta de A para B)
    delta = mesh_a.centroid - mesh_b.centroid
    norm_val = np.linalg.norm(delta)
    normal = delta / norm_val if norm_val > 1e-6 else np.array([0.0, 0.0, 1.0])

    return origin, normal


def find_adjacent_part(
    selected: trimesh.Trimesh,
    others: list,
) -> int:
    """
    Retorna o índice em `others` do mesh mais próximo/adjacente ao `selected`.
    Usa amostragem para performance.
    """
    from scipy.spatial import cKDTree

    sel_verts = np.asarray(selected.vertices, dtype=float)
    step_s = max(1, len(sel_verts) // 2000)
    sel_sample = sel_verts[::step_s]

    min_dist = float("inf")
    best_idx = 0

    for i, mesh in enumerate(others):
        verts = np.asarray(mesh.vertices, dtype=float)
        if len(verts) == 0:
            continue
        step = max(1, len(verts) // 2000)
        sample = verts[::step]
        tree = cKDTree(sample)
        dists, _ = tree.query(sel_sample)
        d = float(dists.min())
        if d < min_dist:
            min_dist = d
            best_idx = i

    return best_idx
