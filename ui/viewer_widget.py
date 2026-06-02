import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
import trimesh

# Paleta de cores para as partes
PART_COLORS = [
    "#4FC3F7", "#EF9A9A", "#A5D6A7", "#FFF176",
    "#CE93D8", "#FFCC80", "#80DEEA", "#F48FB1",
    "#B0BEC5", "#FFAB91", "#C5E1A5", "#B3E5FC",
]


def trimesh_to_pyvista(mesh: trimesh.Trimesh) -> pv.PolyData:
    verts = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    faces_pv = np.hstack([np.full((len(faces), 1), 3, dtype=np.int32), faces]).ravel()
    return pv.PolyData(verts, faces_pv)


class ViewerWidget(QtInteractor):
    """Widget PyVista incorporado no PyQt5 com suporte a click-to-pick."""

    # callback: fn(point: np.ndarray) chamada quando usuário clica na mesh
    on_pick = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_background("#1a1a2e")
        self.add_axes(interactive=False)
        self._actors: dict = {}
        self._plane_actor = None
        self._picking_enabled = False

    # ── Exibição de mesh/partes ───────────────────────────────────────────────

    def show_parts(self, parts: list, names: list, selected_idx: int = -1):
        self._clear_parts()
        for i, (mesh, name) in enumerate(zip(parts, names)):
            color = PART_COLORS[i % len(PART_COLORS)]
            opacity = 1.0 if i == selected_idx or selected_idx == -1 else 0.45
            key = f"part_{i}"
            pv_mesh = trimesh_to_pyvista(mesh)
            self.add_mesh(
                pv_mesh,
                color=color,
                opacity=opacity,
                smooth_shading=True,
                show_edges=False,
                name=key,
            )
            self._actors[key] = True

    def _clear_parts(self):
        for key in list(self._actors.keys()):
            if key.startswith("part_"):
                self.remove_actor(key)
                del self._actors[key]

    # ── Plano de corte (visualização) ────────────────────────────────────────

    def show_cut_plane(self, bounds, axis: str, position: float):
        self.remove_actor("cut_plane")
        lo, hi = bounds[0], bounds[1]
        pad = 1.1

        if axis == "x":
            plane = pv.Plane(
                center=(position, (lo[1]+hi[1])/2, (lo[2]+hi[2])/2),
                direction=(1, 0, 0),
                i_size=(hi[1]-lo[1])*pad,
                j_size=(hi[2]-lo[2])*pad,
            )
        elif axis == "y":
            plane = pv.Plane(
                center=((lo[0]+hi[0])/2, position, (lo[2]+hi[2])/2),
                direction=(0, 1, 0),
                i_size=(hi[0]-lo[0])*pad,
                j_size=(hi[2]-lo[2])*pad,
            )
        else:
            plane = pv.Plane(
                center=((lo[0]+hi[0])/2, (lo[1]+hi[1])/2, position),
                direction=(0, 0, 1),
                i_size=(hi[0]-lo[0])*pad,
                j_size=(hi[1]-lo[1])*pad,
            )

        self._plane_actor = self.add_mesh(
            plane,
            color="#FF6D00",
            opacity=0.28,
            show_edges=True,
            edge_color="#FF6D00",
            name="cut_plane",
        )

    def hide_cut_plane(self):
        self.remove_actor("cut_plane")
        self._plane_actor = None

    # ── Click-to-pick ("conta-gota") ─────────────────────────────────────────

    def enable_picking(self, callback):
        """
        Ativa o modo conta-gota: ao clicar na mesh, `callback(point)` é chamado
        com o ponto 3D em que o usuário clicou.
        """
        self.on_pick = callback
        self._picking_enabled = True
        self.enable_point_picking(
            callback=self._on_point_picked,
            show_message=False,
            use_mesh=True,
            show_point=True,
            point_size=12,
            color="red",
            tolerance=0.025,
        )

    def disable_picking(self):
        self._picking_enabled = False
        self.on_pick = None
        self.disable_picking_all()

    def _on_point_picked(self, point):
        if self.on_pick is not None and point is not None:
            self.on_pick(np.array(point))

    # ── Utilitários ──────────────────────────────────────────────────────────

    def clear_all(self):
        self._clear_parts()
        self.hide_cut_plane()
        self.remove_actor("pick_marker")

    def fit_view(self):
        self.reset_camera()
