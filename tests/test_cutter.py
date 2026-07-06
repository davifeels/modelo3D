"""Testes do módulo de corte — cut_mesh, cut_by_mask, region_grow."""
import numpy as np
import trimesh
import pytest

from src.cutter import (
    cut_mesh, cut_by_mask, _bfs_region, _close_open_mesh,
    split_by_components, get_cross_section_points,
)


# ── cut_mesh ───────────────────────────────────────────────────────────────────

class TestCutMesh:

    @pytest.mark.parametrize("axis", ["x", "y", "z"])
    def test_cut_sphere_all_axes(self, sphere, axis):
        a, b = cut_mesh(sphere, axis, 0.0)
        assert len(a.faces) > 0
        assert len(b.faces) > 0

    def test_cut_preserves_approximate_volume(self, sphere):
        """Volume total das partes deve ser ≈ volume original."""
        a, b = cut_mesh(sphere, 'z', 0.0)
        vol_orig = sphere.volume if sphere.is_watertight else None
        if vol_orig and a.is_watertight and b.is_watertight:
            assert abs((a.volume + b.volume) - vol_orig) / vol_orig < 0.05

    def test_cut_outside_bounds_raises(self, sphere):
        """Corte fora dos limites da mesh deve levantar ValueError."""
        bounds = sphere.bounds
        with pytest.raises(ValueError):
            cut_mesh(sphere, 'z', bounds[1][2] + 10)

    def test_cut_cylinder_z(self, cylinder):
        a, b = cut_mesh(cylinder, 'z', 0.0)
        assert len(a.faces) > 0
        assert len(b.faces) > 0

    def test_cut_cube_x(self, cube):
        a, b = cut_mesh(cube, 'x', 0.0)
        assert len(a.faces) > 0
        assert len(b.faces) > 0


# ── cut_by_mask ────────────────────────────────────────────────────────────────

class TestCutByMask:

    def test_sphere_top_half(self, sphere):
        """Hemisfério pintado → parte pintada em cima, base embaixo."""
        centroids = sphere.triangles_center
        grown_idx = np.where(centroids[:, 2] > 0)[0].astype(np.int64)
        painted, base, origin, normal = cut_by_mask(sphere, grown_idx)
        assert len(painted.faces) > 0
        assert len(base.faces) > 0
        assert painted.centroid[2] > base.centroid[2]
        # Normal aponta da base para a parte pintada (≈ +Z) e é unitária
        assert normal[2] > 0.7
        assert abs(np.linalg.norm(normal) - 1.0) < 1e-6
        # Origin fica na fronteira (equador, z ≈ 0)
        assert abs(origin[2]) < 0.2

    def test_mask_nao_vaza(self, sphere):
        """REGRESSÃO do bug do braço: faces fora da máscara não podem
        migrar para a parte pintada — sem corte planar global."""
        centroids = sphere.triangles_center
        # Calota pequena no topo (análogo ao braço pintado)
        grown_idx = np.where(centroids[:, 2] > 0.7)[0].astype(np.int64)
        assert 0 < len(grown_idx) < len(sphere.faces) // 4
        painted, base, _, _ = cut_by_mask(sphere, grown_idx)
        # Nada da metade de baixo da esfera pode aparecer na parte pintada
        assert painted.bounds[0][2] >= 0.4
        # A base mantém todo o resto da malha (caps podem adicionar faces)
        assert len(base.faces) >= len(sphere.faces) - len(grown_idx)

    def test_all_faces_painted_raises(self, sphere):
        grown_idx = np.arange(len(sphere.faces), dtype=np.int64)
        with pytest.raises(ValueError):
            cut_by_mask(sphere, grown_idx)

    def test_empty_mask_raises(self, sphere):
        with pytest.raises(ValueError):
            cut_by_mask(sphere, np.array([], dtype=np.int64))

    def test_indices_invalidos_filtrados(self, sphere):
        """Índices fora do range são ignorados sem crash."""
        centroids = sphere.triangles_center
        grown_idx = np.where(centroids[:, 2] > 0)[0].astype(np.int64)
        with_bad = np.concatenate([grown_idx, [-5, len(sphere.faces) + 100]])
        painted, base, _, _ = cut_by_mask(sphere, with_bad)
        assert len(painted.faces) > 0
        assert len(base.faces) > 0


class TestBordaIrregular:
    """REGRESSÃO (relato de usuário 2026-07-05): pintura irregular gera
    fronteira não-manifold (pinch points); o cap antigo abandonava anéis
    inteiros → dezenas de arestas abertas na peça exportada ("falhas nas
    bordas") e booleana dos pinos falhando (peça sem encaixe)."""

    def _paint_irregular(self, sphere, seed):
        c = sphere.triangles_center
        rng = np.random.default_rng(seed)
        base = c[:, 2] > 15.0
        jitter = (np.abs(c[:, 2] - 15.0) < 8.0) & (rng.random(len(c)) < 0.5)
        return np.where(base ^ jitter)[0].astype(np.int64)

    @pytest.mark.parametrize("seed", [0, 5, 11])
    def test_pintura_irregular_fecha_watertight(self, seed):
        sphere = trimesh.creation.icosphere(subdivisions=3, radius=50.0)
        idx = self._paint_irregular(sphere, seed)
        painted, base_part, _, _ = cut_by_mask(sphere, idx)
        assert painted.is_watertight, "parte pintada com borda aberta"
        assert base_part.is_watertight, "base com borda aberta"

    def test_pintura_irregular_permite_encaixes(self):
        """Com as partes watertight, a booleana dos pinos deve funcionar."""
        from src.joints import add_joints, JointParams
        sphere = trimesh.creation.icosphere(subdivisions=3, radius=50.0)
        idx = self._paint_irregular(sphere, seed=0)
        a, b, origin, normal = cut_by_mask(sphere, idx)
        params = JointParams(pin_diameter=6.0, pin_depth=8.0, tolerance=1.0, n_pins=1)
        new_a, new_b, warns = add_joints(a, b, origin, normal, params)
        assert new_a.volume > a.volume, f"pino não foi criado: {warns}"
        assert new_b.volume < b.volume, f"cavidade não foi criada: {warns}"
        assert new_a.is_watertight and new_b.is_watertight


# ── _bfs_region ────────────────────────────────────────────────────────────────

class TestBfsRegion:

    def test_grows_contiguous_region(self, cube):
        """BFS deve crescer uma região contígua — usa cubo (faces planas c/ ângulos abruptos)."""
        grown, rest, ratio = _bfs_region(cube, 0, angle_deg=30.0)
        assert len(grown) > 0
        assert len(rest) + len(grown) == len(cube.faces)
        # Cubo tem 6 faces (12 triângulos), ângulo 30° separa pelo menos 1 face
        assert 0.0 < ratio <= 1.0

    def test_tight_angle_gives_small_region(self, sphere):
        grown, _, ratio = _bfs_region(sphere, 0, angle_deg=1.0)
        # Com ângulo mínimo, região deve ser pequena
        assert ratio < 0.5

    def test_wide_angle_gives_large_region(self, sphere):
        grown, _, ratio = _bfs_region(sphere, 0, angle_deg=180.0)
        # Com ângulo máximo, toda a esfera é uma região (superfície suave)
        assert ratio > 0.9

    def test_no_face_left_behind(self, sphere):
        grown, rest, _ = _bfs_region(sphere, 0, angle_deg=45.0)
        all_indices = np.sort(np.concatenate([grown, rest]))
        expected = np.arange(len(sphere.faces), dtype=np.int64)
        np.testing.assert_array_equal(all_indices, expected)


# ── split_by_components ────────────────────────────────────────────────────────

class TestSplitByComponents:

    def test_single_sphere_returns_one(self, sphere):
        parts = split_by_components(sphere)
        assert len(parts) == 1

    def test_two_separate_spheres(self):
        """Dois esferas separadas no espaço → 2 componentes."""
        s1 = trimesh.creation.icosphere(subdivisions=2)
        s2 = trimesh.creation.icosphere(subdivisions=2)
        s2.apply_translation([100, 0, 0])
        combined = trimesh.util.concatenate([s1, s2])
        parts = split_by_components(combined)
        assert len(parts) == 2

    def test_ordered_by_face_count(self):
        s1 = trimesh.creation.icosphere(subdivisions=3)  # 1280 faces
        s2 = trimesh.creation.icosphere(subdivisions=2)  # 320 faces
        s2.apply_translation([100, 0, 0])
        combined = trimesh.util.concatenate([s1, s2])
        parts = split_by_components(combined)
        assert len(parts[0].faces) >= len(parts[1].faces)


# ── get_cross_section_points ───────────────────────────────────────────────────

class TestGetCrossSectionPoints:

    def test_sphere_cross_section_z(self, sphere):
        pts = get_cross_section_points(sphere, 'z', 0.0)
        assert pts.shape[1] == 3
        assert len(pts) > 0

    def test_fallback_outside_bounds(self, sphere):
        """Fora dos limites → retorna fallback sem crash."""
        pts = get_cross_section_points(sphere, 'z', 9999.0)
        assert pts.shape[1] == 3
