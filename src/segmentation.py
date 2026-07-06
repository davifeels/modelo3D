"""
Smart mesh segmentation — totalmente vetorizado, sem loops Python.

Pipeline:
1. Constrói grafo de adjacência em formato CSR (NumPy puro, zero loops Python)
2. BFS compilado via scipy.sparse.csgraph
3. Threshold adaptativo Otsu (vetorizado)
4. Cache do grafo por sessão — primeira chamada constrói, demais são O(1)
"""

from __future__ import annotations
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order
import trimesh


# ── Construção do grafo CSR (zero loops Python) ───────────────────────────────

def _build_csr(mesh: trimesh.Trimesh):
    """
    Constrói grafo de adjacência de faces em formato CSR.
    Pesos = ângulo diedro em graus (float32).
    Totalmente NumPy — sem nenhum loop Python.
    """
    f0  = mesh.face_adjacency[:, 0]     # (M,)
    f1  = mesh.face_adjacency[:, 1]     # (M,)
    ang = np.degrees(mesh.face_adjacency_angles).astype(np.float32)  # (M,)

    n = len(mesh.faces)

    # Duplica as arestas para grafo não-direcionado
    row = np.concatenate([f0, f1])   # (2M,)
    col = np.concatenate([f1, f0])   # (2M,)
    dat = np.concatenate([ang, ang]) # (2M,)

    graph = csr_matrix((dat, (row, col)), shape=(n, n), dtype=np.float32)

    # Sharpness por face = max ângulo com qualquer vizinha (vetorizado via CSR)
    sharpness = np.asarray(graph.max(axis=1).todense()).ravel().astype(np.float32)  # (n,)

    return graph, sharpness


# ── Otsu vetorizado ───────────────────────────────────────────────────────────

def _otsu(values: np.ndarray) -> float:
    if len(values) == 0:
        return 30.0
    hist, edges = np.histogram(values, bins=256)
    centers = (edges[:-1] + edges[1:]) * 0.5
    prob    = hist.astype(np.float64) / hist.sum()

    w0  = np.cumsum(prob)
    mu0 = np.cumsum(prob * centers) / np.where(w0 > 1e-9, w0, 1.0)
    w1  = 1.0 - w0
    mu1 = (np.dot(prob, centers) - np.cumsum(prob * centers)) / np.where(w1 > 1e-9, w1, 1.0)

    var = w0 * w1 * (mu0 - mu1) ** 2
    var[w0 < 1e-9] = -1.0
    var[w1 < 1e-9] = -1.0
    return float(centers[np.argmax(var)])


# ── BFS com máscara de ângulo — vetorizado via scipy ─────────────────────────

def _masked_bfs(graph: csr_matrix, seed: int, threshold: float, max_faces: int) -> np.ndarray:
    """
    BFS a partir de `seed` só atravessa arestas com ângulo < threshold.
    Retorna array de índices das faces alcançadas.
    """
    # Zera arestas acima do threshold (operação vetorizada nos dados CSR)
    masked = graph.copy()
    masked.data[masked.data >= threshold] = 0.0
    masked.eliminate_zeros()

    # BFS compilado em C pelo scipy — retorna nós na ordem de visita
    node_list = breadth_first_order(
        masked, i_start=seed, directed=False, return_predecessors=False
    )

    if len(node_list) > max_faces:
        node_list = node_list[:max_faces]

    return node_list


# ── API pública ───────────────────────────────────────────────────────────────

def suggest_cut_planes(mesh: trimesh.Trimesh, n_slices: int = 100, n_results: int = 5) -> list[dict]:
    """
    Detecta automaticamente os melhores planos de corte por análise de seção transversal.

    Para cada eixo (X, Y, Z): conta faces que cruzam cada posição ao longo do eixo.
    Mínimos locais = "cintura" do modelo = melhor ponto de corte.
    """
    if len(mesh.faces) == 0 or mesh.bounds is None:
        return []

    verts  = np.asarray(mesh.vertices)
    faces  = np.asarray(mesh.faces)
    bounds = mesh.bounds
    results: list[dict] = []

    # Centróides de faces (para cálculo de balanço)
    face_centroids = verts[faces].mean(axis=1)  # (n_faces, 3)

    for axis_idx, axis_name in enumerate(['x', 'y', 'z']):
        mn   = float(bounds[0][axis_idx])
        mx   = float(bounds[1][axis_idx])
        span = mx - mn
        if span < 1.0:
            continue

        margin    = span * 0.1
        positions = np.linspace(mn + margin, mx - margin, n_slices)

        vp = verts[:, axis_idx]
        v0 = vp[faces[:, 0]]
        v1 = vp[faces[:, 1]]
        v2 = vp[faces[:, 2]]
        fc = face_centroids[:, axis_idx]  # centróide de cada face no eixo

        counts = np.array([
            int(np.sum(
                ((v0 <= pos) | (v1 <= pos) | (v2 <= pos)) &
                ((v0 >= pos) | (v1 >= pos) | (v2 >= pos))
            ))
            for pos in positions
        ], dtype=float)

        if counts.max() == 0:
            continue

        norm_counts = counts / counts.max()

        window   = max(3, n_slices // 15)
        smoothed = np.convolve(norm_counts, np.ones(window) / window, mode='same')

        local_mins = _local_minima(smoothed, min_distance=n_slices // 8, min_prominence=0.04)

        for idx in local_mins:
            pos = float(positions[idx])

            # Balanço: proporção de faces em cada lado
            n_left  = int(np.sum(fc < pos))
            n_right = int(np.sum(fc >= pos))
            total   = n_left + n_right
            balance = min(n_left, n_right) / total if total > 0 else 0.0
            # Penaliza fortemente cortes muito desequilibrados (< 5% em um lado)
            balance_score = 4.0 * balance * (1.0 - balance)  # 1.0 em 50/50, 0 em 0/100

            thinness      = 1.0 - smoothed[idx]
            rel_pos       = (pos - mn) / span
            center_bonus  = 1.0 - 2.0 * abs(rel_pos - 0.5)
            final_score   = thinness * 0.45 + balance_score * 0.35 + center_bonus * 0.20

            results.append({
                'axis':           axis_name,
                'position':       pos,
                'score':          float(final_score),
                'crossing_count': int(counts[idx]),
                'balance':        round(float(balance), 3),
            })

    results.sort(key=lambda r: -r['score'])
    return results[:n_results]


def _local_minima(arr: np.ndarray, min_distance: int = 5, min_prominence: float = 0.05) -> list[int]:
    """Mínimos locais com filtragem por distância mínima e prominência."""
    n = len(arr)
    candidates = []
    for i in range(1, n - 1):
        if arr[i] <= arr[i-1] and arr[i] <= arr[i+1]:
            candidates.append(i)

    filtered: list[int] = []
    for i in candidates:
        if filtered and i - filtered[-1] < min_distance:
            if arr[i] < arr[filtered[-1]]:
                filtered[-1] = i
        else:
            filtered.append(i)

    result = []
    for i in filtered:
        lo        = max(0, i - min_distance * 3)
        hi        = min(n, i + min_distance * 3)
        left_max  = float(arr[lo:i].max())   if i > lo   else 0.0
        right_max = float(arr[i+1:hi].max()) if i+1 < hi else 0.0
        prominence = max(left_max, right_max) - arr[i]
        if prominence >= min_prominence:
            result.append(i)

    return result


def smart_segment(
    mesh: trimesh.Trimesh,
    seed_face_idx: int,
    max_region_pct: float = 0.6,
    min_region_pct: float = 0.01,
    _graph_cache: dict | None = None,
) -> list[int]:
    """
    Detecta a região semântica ao redor de seed_face_idx.
    _graph_cache: dict por sessão — guarda grafo CSR entre chamadas.
    """
    n_faces = len(mesh.faces)
    if n_faces == 0 or seed_face_idx >= n_faces:
        return [seed_face_idx]

    # Reutiliza grafo cacheado se disponível
    if _graph_cache is not None and 'csr' in _graph_cache:
        graph, sharpness = _graph_cache['csr']
    else:
        graph, sharpness = _build_csr(mesh)
        if _graph_cache is not None:
            _graph_cache['csr'] = (graph, sharpness)

    # Threshold local: Otsu sobre vizinhança imediata (2-hop)
    seed_row   = graph.getrow(seed_face_idx)
    local_ang  = seed_row.data
    if len(local_ang) > 5:
        # Expande para 2-hop para ter mais amostras
        neighbors_1hop = seed_row.indices
        rows = graph[neighbors_1hop, :]
        local_ang = np.concatenate([local_ang, rows.data])

    if len(local_ang) > 10:
        threshold = _otsu(local_ang)
    else:
        threshold = _otsu(sharpness)

    threshold = float(np.clip(threshold, 10.0, 90.0))

    max_f = int(n_faces * max_region_pct)
    min_f = int(n_faces * min_region_pct)

    region = _masked_bfs(graph, seed_face_idx, threshold, max_f)

    # Fallback progressivo se região muito pequena
    attempts = 0
    while len(region) < min_f and attempts < 5:
        threshold = min(threshold * 1.6, 160.0)
        region    = _masked_bfs(graph, seed_face_idx, threshold, max_f)
        attempts += 1

    return region.tolist()
