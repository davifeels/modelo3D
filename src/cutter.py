import trimesh
import numpy as np

AXIS_NORMALS = {
    "x": np.array([1.0, 0.0, 0.0]),
    "y": np.array([0.0, 1.0, 0.0]),
    "z": np.array([0.0, 0.0, 1.0]),
}
AXIS_IDX = {"x": 0, "y": 1, "z": 2}


def cut_mesh(mesh: trimesh.Trimesh, axis: str, position: float):
    """
    Corta a mesh no eixo/posição dados.
    Retorna (parte_positiva, parte_negativa).
    """
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

    # fallback: centro do bounding box projetado no plano
    c = mesh.centroid.copy()
    c[AXIS_IDX[axis]] = position
    return c
