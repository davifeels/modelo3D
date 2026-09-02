import trimesh
import numpy as np

# Detecta se rtree está disponível para cap=True
try:
    import rtree  # noqa: F401
    _CAP = True
except ImportError:
    _CAP = False


def _slice(mesh, normal, origin):
    """slice_mesh_plane com cap=True se rtree disponível, senão cap=False."""
    try:
        return trimesh.intersections.slice_mesh_plane(mesh, normal, origin, cap=_CAP)
    except ImportError:
        return trimesh.intersections.slice_mesh_plane(mesh, normal, origin, cap=False)

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

    part_pos = _slice(mesh, normal, origin)
    part_neg = _slice(mesh, -normal, origin)

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

def _boundary_simple_cycles(boundary: np.ndarray) -> list:
    """
    Decompõe as arestas de fronteira direcionadas em CICLOS SIMPLES
    (sem vértice repetido), consumindo cada aresta exatamente uma vez.

    Fronteiras de pintura real são frequentemente não-manifold: dois lóbulos
    da seleção se tocam num único vértice ("pinch"). Travessia por VÉRTICE
    (dict a→b) perde arestas paralelas e abandona anéis inteiros — era a
    causa das bordas abertas na exportação. Travessia por ARESTA com split
    nos pinch points fecha todo o conjunto.
    """
    from collections import defaultdict

    out = defaultdict(list)
    for a, b in boundary:
        out[int(a)].append(int(b))

    cycles = []
    for start in list(out.keys()):
        while out[start]:
            path = [start]
            pos = {start: 0}
            while True:
                cur = path[-1]
                if not out[cur]:
                    break                    # cadeia aberta (degenerada) — abandona
                nxt = out[cur].pop()
                if nxt in pos:
                    i = pos[nxt]
                    cycle = path[i:]         # ciclo simples nxt..cur
                    if len(cycle) >= 3:
                        cycles.append(cycle)
                    for v in path[i + 1:]:
                        del pos[v]
                    path = path[:i + 1]
                    if len(path) == 1 and not out[path[0]]:
                        break
                else:
                    path.append(nxt)
                    pos[nxt] = len(path) - 1
    return cycles


def _cap_boundary_loops(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Fecha cada anel de fronteira aberto com um leque de triângulos até o
    centróide do anel. Anéis não-manifold (pinch points) são divididos em
    ciclos simples antes — cada aresta de fronteira recebe exatamente uma
    tampa, garantindo malha watertight ao final.
    """
    from trimesh import grouping

    edges = mesh.edges                       # direcionadas, seguindo o winding das faces
    edges_sorted = np.sort(edges, axis=1)
    unique_rows = grouping.group_rows(edges_sorted, require_count=1)
    if len(unique_rows) == 0:
        return mesh

    boundary = edges[unique_rows]            # (M, 2) arestas de fronteira direcionadas

    verts = np.asarray(mesh.vertices)
    new_verts = []
    new_faces = []

    for loop in _boundary_simple_cycles(boundary):
        center = verts[loop].mean(axis=0)
        ci = len(verts) + len(new_verts)
        new_verts.append(center)
        # (b, a, centro): winding oposto ao da aresta de fronteira → normal para fora
        for a, b in zip(loop, loop[1:] + loop[:1]):
            new_faces.append([b, a, ci])

    if not new_faces:
        return mesh

    capped = trimesh.Trimesh(
        vertices=np.vstack([verts, np.array(new_verts)]),
        faces=np.vstack([np.asarray(mesh.faces), np.array(new_faces, dtype=np.int64)]),
        process=False,
    )
    capped.process(validate=False)
    return capped


def _close_open_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Fecha buracos abertos numa mesh.
    Tenta trimesh primeiro (rápido), depois fan cap dos anéis de fronteira
    (determinístico), depois PyVista (fallback para casos complexos).
    """
    # Tentativa 1: trimesh repair (funciona bem para buracos pequenos).
    # Em CÓPIA — fill_holes muta in-place e, quando falha parcialmente,
    # deixa a malha num estado que quebra as tentativas seguintes.
    try:
        candidate = mesh.copy()
        trimesh.repair.fill_holes(candidate)
        if candidate.is_watertight:
            return candidate
    except Exception:
        pass

    # Tentativa 2: fan cap determinístico nos anéis de fronteira
    try:
        capped = _cap_boundary_loops(mesh)
        if capped.is_watertight:
            return capped
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


def cut_by_mask(mesh: trimesh.Trimesh, painted_idx) -> tuple:
    """
    Separação definitiva por máscara de faces:
    - parte pintada = exatamente as faces em painted_idx
    - parte base    = todas as demais faces
    Sem plano de corte, sem PCA, sem semi-espaço — a pintura É a seleção.

    A fronteira aberta de cada submalha é fechada com cap local
    (_close_open_mesh). Retorna (part_painted, part_base, origin, normal),
    onde origin/normal são apenas metadados da interface para posicionar
    encaixes: origin = centro dos vértices de fronteira pintado/não-pintado,
    normal = direção do centróide da base para o centróide da parte pintada.
    """
    n_faces = len(mesh.faces)
    painted_idx = np.unique(np.asarray(painted_idx, dtype=np.int64))
    painted_idx = painted_idx[(painted_idx >= 0) & (painted_idx < n_faces)]

    mask = np.zeros(n_faces, dtype=bool)
    mask[painted_idx] = True
    rest_idx = np.nonzero(~mask)[0]

    if len(painted_idx) == 0:
        raise ValueError("Nenhuma face pintada válida.")
    if len(rest_idx) == 0:
        raise ValueError("Todas as faces foram pintadas — nada para separar.")

    faces = np.asarray(mesh.faces)
    verts = np.asarray(mesh.vertices)

    # Metadados da interface (para encaixes) — calculados antes dos caps
    painted_verts = np.unique(faces[mask].ravel())
    rest_verts = np.unique(faces[~mask].ravel())
    boundary = np.intersect1d(painted_verts, rest_verts, assume_unique=True)

    painted_centroid = verts[painted_verts].mean(axis=0)
    rest_centroid = verts[rest_verts].mean(axis=0)

    if len(boundary) > 0:
        origin = verts[boundary].mean(axis=0)
    else:
        # Região pintada é um shell desconexo — interface = ponto médio
        origin = (painted_centroid + rest_centroid) / 2.0

    delta = painted_centroid - rest_centroid
    norm_len = np.linalg.norm(delta)
    normal = delta / norm_len if norm_len > 1e-9 else np.array([0.0, 0.0, 1.0])

    part_painted = mesh.submesh([painted_idx], append=True)
    part_base = mesh.submesh([rest_idx], append=True)

    # Fecha a costura na fronteira da pintura (cap local — não é corte)
    part_painted = _close_open_mesh(part_painted)
    part_base = _close_open_mesh(part_base)

    if part_painted is None or len(part_painted.faces) == 0:
        raise ValueError("Separação gerou parte pintada vazia.")
    if part_base is None or len(part_base.faces) == 0:
        raise ValueError("Separação gerou base vazia.")

    return part_painted, part_base, origin, normal


def _is_valid_region_volume(mesh: trimesh.Trimesh, labels: np.ndarray, rid) -> bool:
    """
    True se a região `rid`, uma vez fechada (_close_open_mesh), forma um
    sólido válido para booleanas — mesmo teste (`is_volume`) que o engine
    manifold usa internamente; sua falha é o "Not all meshes are volumes!"
    que quebra a geração de encaixes.
    """
    idx = np.nonzero(labels == rid)[0]
    if len(idx) == 0:
        return False
    part = _close_open_mesh(mesh.submesh([idx], append=True))
    return bool(part is not None and len(part.faces) > 0 and part.is_volume)


def _merge_degenerate_regions(mesh: trimesh.Trimesh, labels: np.ndarray) -> np.ndarray:
    """
    Funde regiões que NÃO formam um sólido válido (ver _is_valid_region_volume)
    na vizinha VÁLIDA com maior fronteira compartilhada — mesma heurística de
    segmentation._merge_small_regions, mas pelo critério "é um sólido real?"
    em vez de contagem de faces.

    Acontece com "caps" planos isolados por uma quina de 90°: ex. a base de
    uma perna cilíndrica virando sua própria região (a região da parede
    lateral já fecha sozinha num cilindro completo via _close_open_mesh —
    o cap isolado é redundante e, sozinho, é uma chapa de volume ~0). Sem
    esta fusão, cut_by_multi_mask geraria uma "peça" não imprimível e sem
    encaixe possível.
    """
    labels = labels.copy()
    fa = mesh.face_adjacency

    ids = np.unique(labels)
    degenerate = [int(rid) for rid in ids if not _is_valid_region_volume(mesh, labels, rid)]
    if not degenerate:
        return labels

    for sid in degenerate:
        if not np.any(labels == sid):
            continue  # já foi fundida junto com outra região degenerada
        la, lb = labels[fa[:, 0]], labels[fa[:, 1]]
        touching = np.concatenate([
            lb[(la == sid) & (lb != sid)],
            la[(lb == sid) & (la != sid)],
        ])
        valid_touch = touching[~np.isin(touching, degenerate)]
        pool = valid_touch if len(valid_touch) > 0 else touching
        if len(pool) > 0:
            n_ids, n_counts = np.unique(pool, return_counts=True)
            target = int(n_ids[np.argmax(n_counts)])
        else:
            # fragmento isolado sem vizinhos -- funde na maior região atual
            rem_ids, sizes = np.unique(labels, return_counts=True)
            others_mask = rem_ids != sid
            if not np.any(others_mask):
                continue  # única região restante -- nada a fundir
            target = int(rem_ids[others_mask][np.argmax(sizes[others_mask])])
        labels[labels == sid] = target

    return labels


def cut_by_multi_mask(mesh: trimesh.Trimesh, labels) -> tuple:
    """
    Divide a malha em N partes — uma por região da máscara (§1, modo
    Professional). Cada parte é fechada com caps (_close_open_mesh).
    Regiões sem volume real (ver _merge_degenerate_regions) são fundidas
    na vizinha antes do corte final.

    Retorna (parts, interfaces, region_ids):
    - parts: lista de Trimesh, parts[i] corresponde à região region_ids[i]
    - interfaces: [{'region_a', 'region_b', 'origin', 'normal'}] por par de
      regiões adjacentes. Convenção dos encaixes: A = região MAIOR (recebe
      pinos), B = menor (cavidades); normal aponta de B para A.
    - region_ids: ids finais das regiões (após _merge_degenerate_regions) —
      NÃO são necessariamente 0..k-1 nem os ids originais em `labels": uma
      fusão pode deixar buracos (ex.: sobra {0, 2, 4}). `region_a`/
      `region_b` em cada interface sempre referenciam um id desta lista —
      chamadores não devem recalcular ids a partir do `labels` de entrada.
    """
    labels = np.asarray(labels, dtype=np.int64)
    n_faces = len(mesh.faces)
    if len(labels) != n_faces:
        raise ValueError(f"labels tem {len(labels)} entradas; a malha tem {n_faces} faces.")
    region_ids = np.unique(labels)
    if len(region_ids) < 2:
        raise ValueError("A máscara precisa de pelo menos 2 regiões.")

    labels = _merge_degenerate_regions(mesh, labels)
    region_ids = np.unique(labels)
    if len(region_ids) < 2:
        raise ValueError(
            "Após descartar regiões sem volume real (ex.: uma tampa plana "
            "isolada por uma quina), restou menos de 2 regiões válidas."
        )

    verts = np.asarray(mesh.vertices)

    parts = []
    for rid in region_ids:
        idx = np.nonzero(labels == rid)[0]
        part = _close_open_mesh(mesh.submesh([idx], append=True))
        if part is None or len(part.faces) == 0:
            raise ValueError(f"Região {rid} gerou parte vazia.")
        parts.append(part)

    # Interfaces: pares de regiões com arestas de adjacência cruzando
    fa = mesh.face_adjacency
    fe = mesh.face_adjacency_edges
    la, lb = labels[fa[:, 0]], labels[fa[:, 1]]
    cross = la != lb
    interfaces = []
    if np.any(cross):
        pair_lo = np.minimum(la[cross], lb[cross])
        pair_hi = np.maximum(la[cross], lb[cross])
        pair_edges = fe[cross]
        for lo, hi in {(int(a), int(b)) for a, b in zip(pair_lo, pair_hi)}:
            sel = (pair_lo == lo) & (pair_hi == hi)
            pts = verts[np.unique(pair_edges[sel].ravel())]
            origin = pts.mean(axis=0)

            # Plano da fronteira via SVD; degenera → delta de centróides
            centered = pts - origin
            normal = None
            if len(pts) >= 3:
                try:
                    _, sv, Vt = np.linalg.svd(centered, full_matrices=False)
                    if sv[-1] < sv[0] * 0.9:   # fronteira razoavelmente planar
                        normal = Vt[-1]
                except Exception:
                    pass

            # A = região maior (pinos); B = menor (cavidades)
            size_lo = int((labels == lo).sum())
            size_hi = int((labels == hi).sum())
            ra, rb = (lo, hi) if size_lo >= size_hi else (hi, lo)
            cen_a = verts[np.unique(np.asarray(mesh.faces)[labels == ra].ravel())].mean(axis=0)
            cen_b = verts[np.unique(np.asarray(mesh.faces)[labels == rb].ravel())].mean(axis=0)
            delta = cen_a - cen_b
            if normal is None:
                nl = np.linalg.norm(delta)
                normal = delta / nl if nl > 1e-9 else np.array([0.0, 0.0, 1.0])
            elif normal.dot(delta) < 0:
                normal = -normal   # orienta de B → A

            interfaces.append({
                "region_a": int(ra), "region_b": int(rb),
                "origin": origin, "normal": np.asarray(normal, dtype=float),
            })

    return parts, interfaces, [int(r) for r in region_ids]


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


def region_grow_and_cut(
    mesh: trimesh.Trimesh,
    point: np.ndarray,
    angle_deg: float = 30.0,
) -> tuple:
    """
    "Varinha mágica" 3D com separação por máscara:
    1. Detecta a região pelo ângulo diedro (region growing)
    2. Separa exatamente as faces da região (cut_by_mask) — sem plano de corte
    3. Fecha a fronteira de cada parte com cap local

    Retorna (parte_pintada, parte_base, origin, normal) — origin/normal são
    metadados da interface para posicionar encaixes, não um plano de corte.
    Lança ValueError se a região for trivial.
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

    return cut_by_mask(mesh, grown_idx)


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
