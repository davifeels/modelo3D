import trimesh
import numpy as np
from pathlib import Path


def load_mesh(path: str):
    path = Path(path)
    raw = trimesh.load(str(path), force="mesh")

    if isinstance(raw, trimesh.Scene):
        meshes = [g for g in raw.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("Nenhuma malha encontrada no arquivo.")
        raw = trimesh.util.concatenate(meshes)

    if not isinstance(raw, trimesh.Trimesh):
        raise ValueError("Formato não suportado.")

    raw.remove_duplicate_faces()
    raw.remove_degenerate_faces()

    bounds = raw.bounds
    dims = bounds[1] - bounds[0]

    info = {
        "name": path.name,
        "vertices": len(raw.vertices),
        "faces": len(raw.faces),
        "dims_mm": dims,
        "center": raw.centroid,
        "bounds": bounds,
        "is_watertight": raw.is_watertight,
    }
    return raw, info
