import trimesh
import numpy as np
from dataclasses import dataclass


@dataclass
class JointParams:
    pin_diameter: float = 3.0    # mm
    pin_depth: float = 8.0       # mm
    tolerance: float = 0.2       # mm — folga no furo
    n_pins: int = 1


def _cylinder_transform(direction: np.ndarray, center: np.ndarray) -> np.ndarray:
    direction = direction / np.linalg.norm(direction)
    R = trimesh.geometry.align_vectors(np.array([0.0, 0.0, 1.0]), direction)
    T = np.eye(4)
    T[:3, :3] = R[:3, :3]
    T[:3, 3] = center
    return T


def _make_pin(radius: float, depth: float, origin: np.ndarray, normal: np.ndarray) -> trimesh.Trimesh:
    pin = trimesh.creation.cylinder(radius=radius, height=depth, sections=32)
    center = origin + normal * (depth / 2.0)
    pin.apply_transform(_cylinder_transform(normal, center))
    return pin


def _make_hole(radius: float, depth: float, origin: np.ndarray, normal: np.ndarray) -> trimesh.Trimesh:
    hole = trimesh.creation.cylinder(radius=radius, height=depth + 1.0, sections=32)
    center = origin - normal * (depth / 2.0)
    hole.apply_transform(_cylinder_transform(-normal, center))
    return hole


def _offsets_for_n_pins(n: int, cut_section_pts: np.ndarray, normal: np.ndarray) -> list:
    if n == 1 or len(cut_section_pts) == 0:
        center = cut_section_pts.mean(axis=0) if len(cut_section_pts) > 0 else np.zeros(3)
        return [center]

    centroid = cut_section_pts.mean(axis=0)

    # Vetor perpendicular ao normal no plano do corte
    perp = np.array([-normal[1], normal[2], normal[0]])
    perp -= perp.dot(normal) * normal
    if np.linalg.norm(perp) < 1e-6:
        perp = np.array([normal[2], -normal[0], normal[1]])
        perp -= perp.dot(normal) * normal
    perp /= np.linalg.norm(perp)

    projections = cut_section_pts.dot(perp)
    mn, mx = projections.min(), projections.max()
    span = mx - mn
    mean_proj = projections.mean()

    offsets = []
    for i in range(n):
        t = (i + 1) / (n + 1)
        offsets.append(centroid + perp * (mn + t * span - mean_proj))
    return offsets


def add_joints(
    part_a: trimesh.Trimesh,
    part_b: trimesh.Trimesh,
    cut_origin: np.ndarray,
    normal: np.ndarray,
    params: JointParams,
    cut_section_pts: np.ndarray = None,
):
    """
    Adiciona pino(s) em part_a e furo(s) correspondentes em part_b.
    normal aponta de part_b → part_a.
    Retorna (part_a_modificada, part_b_modificada, lista_de_avisos).
    """
    normal = normal / np.linalg.norm(normal)
    pin_r = params.pin_diameter / 2.0
    hole_r = pin_r + params.tolerance
    depth = params.pin_depth

    if cut_section_pts is None or len(cut_section_pts) == 0:
        cut_section_pts = np.array([cut_origin])

    origins = _offsets_for_n_pins(params.n_pins, cut_section_pts, normal)

    result_a = part_a
    result_b = part_b
    warnings = []

    for i, origin in enumerate(origins):
        pin = _make_pin(pin_r, depth, origin, normal)
        hole = _make_hole(hole_r, depth, origin, normal)

        try:
            result_a = trimesh.boolean.union([result_a, pin], engine="manifold")
        except Exception as e:
            warnings.append(f"Pino {i+1} não foi adicionado: {e}")

        try:
            result_b = trimesh.boolean.difference([result_b, hole], engine="manifold")
        except Exception as e:
            warnings.append(f"Furo {i+1} não foi feito: {e}")

    return result_a, result_b, warnings
