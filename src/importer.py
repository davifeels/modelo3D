import trimesh
import numpy as np
from pathlib import Path
import threading

from src import config as cfg
from src import logger as log_mod

_log = log_mod.get()

HEAVY_MESH_THRESHOLD: int = cfg.get("mesh", "heavy_threshold_faces", 500_000)

_SPLIT_MAX_FACES  = 150_000
_REPAIR_MAX_FACES = 50_000


def _run_with_timeout(fn, timeout, *args):
    """
    Executa fn em thread separada com timeout.
    Retorna (result, ok). Se timeout → (None, False).
    IMPORTANTE: só usar para operações que NÃO modificam objetos externos em place,
    pois modificações in-place em threads podem ter visibilidade indeterminada no Windows.
    """
    result = [None]
    error  = [None]
    done   = threading.Event()

    def _target():
        try:
            result[0] = fn(*args)
        except Exception as e:
            error[0] = e
        finally:
            done.set()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    if not done.wait(timeout):
        _log.warning("Timeout (%.1fs) em operação — pulando", timeout)
        return None, False
    if error[0]:
        raise error[0]
    return result[0], True


def load_mesh(path: str):
    """
    Carregamento rápido. merge_vertices e split são chamados direto (são rápidos).
    Repair tem timeout pois fix_normals pode ser lento em meshes grandes.
    """
    path = Path(path)
    _log.info("Carregando: %s", path)

    raw = trimesh.load(str(path), force="mesh", process=False)

    if isinstance(raw, trimesh.Scene):
        meshes = [g for g in raw.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("Nenhuma malha encontrada no arquivo.")
        raw = trimesh.util.concatenate(meshes)

    if not isinstance(raw, trimesh.Trimesh):
        raise ValueError("Formato não suportado.")

    # merge_vertices é rápido (< 100ms mesmo para 500k faces) — chamada direta
    try:
        raw.merge_vertices()
    except Exception as e:
        _log.warning("merge_vertices falhou: %s", e)

    n_faces = len(raw.faces)
    n_verts = len(raw.vertices)
    _log.info("Após merge: %d faces, %d verts", n_faces, n_verts)

    # trimesh.load NÃO levanta exceção para arquivo vazio/corrompido/lixo
    # binário — devolve um Trimesh válido só que com 0 faces. Sem este
    # guard, o código seguia adiante e só quebrava várias linhas depois
    # (bounds=None em mesh vazia) com um TypeError sem relação nenhuma
    # com a causa real ("arquivo inválido").
    if n_faces == 0 or n_verts == 0:
        raise ValueError("Arquivo não contém uma malha 3D válida (0 faces).")

    # ── Repair (só meshes pequenas, com timeout) ──────────────────────────────
    is_wt = False
    was_repaired = False
    if n_faces < _REPAIR_MAX_FACES:
        def _do_repair():
            trimesh.repair.fix_normals(raw)
            trimesh.repair.fix_winding(raw)
            wt = bool(raw.is_watertight)
            repaired = False
            if not wt:
                # Fecha buracos pequenos (briefing seção 8). fill_holes do
                # trimesh só fecha buracos de 3-4 lados — rápido e seguro.
                try:
                    trimesh.repair.fill_holes(raw)
                    wt = bool(raw.is_watertight)
                    repaired = wt
                except Exception:
                    pass
            return wt, repaired

        result, ok = _run_with_timeout(_do_repair, 8.0)
        if ok and result is not None:
            is_wt, was_repaired = result
        else:
            try:
                is_wt = bool(raw.is_watertight)
            except Exception:
                pass
    else:
        try:
            is_wt = bool(raw.is_watertight)
        except Exception:
            pass

    # ── Split em componentes ──────────────────────────────────────────────────
    # split() é rápido (< 100ms) após merge_vertices — chamada direta
    if n_faces <= _SPLIT_MAX_FACES:
        try:
            components = _split_components(raw)
        except Exception as e:
            _log.warning("split falhou: %s — usando mesh inteira", e)
            components = [raw]
    else:
        components = [raw]

    n_comp = len(components)
    _log.info("%d componente(s)", n_comp)

    bounds = raw.bounds
    dims   = bounds[1] - bounds[0]
    max_d  = float(dims.max())

    # Detecta e auto-escala para mm
    # Objetos impressos em 3D: geralmente 10–500mm.
    # Se max_d < 10 → provavelmente em metros → ×1000
    # Se max_d > 10000 → provavelmente em µm → ×0.001
    if max_d < 10:
        scale = 1000.0
        unit_hint = "m"
    elif max_d > 10000:
        scale = 0.001
        unit_hint = "µm"
    elif max_d > 500:
        scale = 10.0
        unit_hint = "cm"
    else:
        scale = 1.0
        unit_hint = "mm"

    scaled_from = unit_hint if scale != 1.0 else None
    if scale != 1.0:
        # Escala apenas os components (podem ser o próprio raw quando mesh é pesada)
        scaled_ids = set()
        for c in components:
            if id(c) not in scaled_ids:
                c.apply_scale(scale)
                scaled_ids.add(id(c))
        # Escala raw só se não foi escalado via components
        if id(raw) not in scaled_ids:
            raw.apply_scale(scale)
        dims = dims * scale
        max_d = float(dims.max())

    volume_cm3 = None
    if is_wt:
        try:
            v = float(raw.volume)
            # Sanity: volume não pode exceder bounding box (em mm³).
            # Margem de 0.5% cobre o caso degenerado volume == bbox (caixa).
            bbox_vol = float(dims[0] * dims[1] * dims[2])
            if 0 < v <= bbox_vol * 1.005 and v < 1e9:
                volume_cm3 = round(v / 1000.0, 2)
        except Exception:
            pass

    info = {
        "name":          path.name,
        "vertices":      n_verts,
        "faces":         n_faces,
        "dims_mm":       dims,
        "center":        raw.centroid,
        "bounds":        bounds,
        "is_watertight": is_wt,
        "was_repaired":  was_repaired,
        "n_components":  n_comp,
        "is_heavy":      n_faces > HEAVY_MESH_THRESHOLD,
        "unit_hint":     unit_hint,
        "scaled_from":   scaled_from,
        "volume_cm3":    volume_cm3,
    }
    return components, info


def _split_components(mesh: trimesh.Trimesh) -> list:
    """Divide em componentes conectados."""
    try:
        from src.cutter import split_by_components
        return split_by_components(mesh)
    except Exception as e:
        _log.warning("split falhou: %s", e)
        return [mesh]
