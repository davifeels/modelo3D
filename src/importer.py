import trimesh
import numpy as np
from pathlib import Path
from src.cutter import split_by_components

# Limiar para alertar sobre modelos pesados (faces)
HEAVY_MESH_THRESHOLD = 500_000
# Alvo padrão de simplificação (faces)
SIMPLIFY_TARGET = 200_000


def load_mesh(path: str):
    """
    Carrega STL/OBJ e divide automaticamente em componentes conectados.
    Retorna (list[Trimesh], info_dict).
    info_dict inclui 'is_heavy': True se faces > HEAVY_MESH_THRESHOLD.
    """
    path = Path(path)
    raw = trimesh.load(str(path), force="mesh")

    if isinstance(raw, trimesh.Scene):
        meshes = [g for g in raw.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("Nenhuma malha encontrada no arquivo.")
        raw = trimesh.util.concatenate(meshes)

    if not isinstance(raw, trimesh.Trimesh):
        raise ValueError("Formato não suportado.")

    n_faces = len(raw.faces)
    components = split_by_components(raw)

    bounds = raw.bounds
    dims = bounds[1] - bounds[0]

    # Detecta unidade provável pelo tamanho do modelo
    max_dim = float(dims.max())
    if max_dim > 500:
        unit_hint = "cm (modelo grande — considere converter para mm)"
    elif max_dim < 1:
        unit_hint = "m (modelo pequeno — pode estar em metros)"
    else:
        unit_hint = "mm"

    info = {
        "name": path.name,
        "vertices": len(raw.vertices),
        "faces": n_faces,
        "dims_mm": dims,
        "center": raw.centroid,
        "bounds": bounds,
        "is_watertight": raw.is_watertight,
        "n_components": len(components),
        "is_heavy": n_faces > HEAVY_MESH_THRESHOLD,
        "unit_hint": unit_hint,
    }
    return components, info
