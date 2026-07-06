"""Testes do módulo de encaixes — add_joints, _offsets_for_n_pins."""
import numpy as np
import trimesh
import pytest

from src.joints import (
    add_joints, JointParams, _offsets_for_n_pins, _make_pin, _make_hole,
    _male_solids, _female_solids, JOINT_TYPES, apply_joint_specs,
)


# ── _make_pin / _make_hole ─────────────────────────────────────────────────────

class TestMakeGeometry:

    def test_pin_has_faces(self):
        pin = _make_pin(1.5, 8.0, np.zeros(3), np.array([0., 0., 1.]))
        assert len(pin.faces) > 0

    def test_hole_has_faces(self):
        hole = _make_hole(1.7, 8.0, np.zeros(3), np.array([0., 0., 1.]))
        assert len(hole.faces) > 0

    @pytest.mark.parametrize("normal", [
        [0., 0., 1.],
        [1., 0., 0.],
        [0., 1., 0.],
        [0.577, 0.577, 0.577],  # diagonal
    ])
    def test_pin_all_normals(self, normal):
        """Pino não deve crashar para nenhuma direção."""
        n = np.array(normal, dtype=float)
        n /= np.linalg.norm(n)
        pin = _make_pin(1.5, 8.0, np.zeros(3), n)
        assert len(pin.faces) > 0


# ── _offsets_for_n_pins ────────────────────────────────────────────────────────

class TestOffsets:

    def test_single_pin_at_centroid(self):
        pts = np.random.randn(100, 3)
        normal = np.array([0., 0., 1.])
        offsets = _offsets_for_n_pins(1, pts, normal)
        assert len(offsets) == 1
        np.testing.assert_allclose(offsets[0], pts.mean(axis=0), atol=1e-6)

    def test_n_pins_returns_n_offsets(self):
        pts = np.random.randn(200, 3)
        normal = np.array([0., 0., 1.])
        for n in [1, 2, 3, 4]:
            offsets = _offsets_for_n_pins(n, pts, normal)
            assert len(offsets) == n

    def test_empty_pts_no_crash(self):
        offsets = _offsets_for_n_pins(1, np.zeros((0, 3)), np.array([0., 0., 1.]))
        assert len(offsets) == 1


# ── add_joints ─────────────────────────────────────────────────────────────────

class TestAddJoints:

    def _halves(self, mesh):
        import trimesh.intersections as ti
        n = np.array([0., 0., 1.])
        o = np.zeros(3)
        top = ti.slice_mesh_plane(mesh, n, o, cap=True)
        bot = ti.slice_mesh_plane(mesh, -n, o, cap=True)
        return top, bot

    def test_result_a_has_faces(self, sphere):
        top, bot = self._halves(sphere)
        params = JointParams(pin_diameter=2.0, pin_depth=6.0, tolerance=0.2, n_pins=1)
        new_a, new_b, warnings = add_joints(top, bot, np.zeros(3), np.array([0.,0.,1.]), params)
        assert len(new_a.faces) > 0, f"part_a ficou vazia! warnings={warnings}"

    def test_result_b_has_faces(self, sphere):
        """Bug crítico corrigido: part_b não pode ficar com 0 faces."""
        top, bot = self._halves(sphere)
        params = JointParams(pin_diameter=2.0, pin_depth=6.0, tolerance=0.2, n_pins=1)
        new_a, new_b, warnings = add_joints(top, bot, np.zeros(3), np.array([0.,0.,1.]), params)
        assert len(new_b.faces) > 0, f"part_b ficou vazia! warnings={warnings}"

    def test_warnings_are_strings(self, sphere):
        top, bot = self._halves(sphere)
        params = JointParams()
        _, _, warnings = add_joints(top, bot, np.zeros(3), np.array([0.,0.,1.]), params)
        assert all(isinstance(w, str) for w in warnings)

    def test_cylinder_halves(self, cylinder):
        top, bot = self._halves(cylinder)
        params = JointParams(pin_diameter=3.0, pin_depth=8.0, tolerance=0.2, n_pins=1)
        new_a, new_b, warnings = add_joints(top, bot, np.zeros(3), np.array([0.,0.,1.]), params)
        assert len(new_a.faces) > 0
        assert len(new_b.faces) > 0

    def test_non_z_normal(self, sphere):
        """Encaixe em normal não-Z não deve crashar."""
        import trimesh.intersections as ti
        normal = np.array([1., 0., 0.])
        top = ti.slice_mesh_plane(sphere, normal, np.zeros(3), cap=True)
        bot = ti.slice_mesh_plane(sphere, -normal, np.zeros(3), cap=True)
        params = JointParams(pin_diameter=2.0, pin_depth=6.0, tolerance=0.2, n_pins=1)
        new_a, new_b, warnings = add_joints(top, bot, np.zeros(3), normal, params)
        assert len(new_a.faces) > 0
        assert len(new_b.faces) > 0

    def test_multiple_pins(self, cylinder):
        """2 pinos não devem crashar nem deixar mesh vazia."""
        top, bot = self._halves(cylinder)
        params = JointParams(pin_diameter=2.0, pin_depth=6.0, tolerance=0.2, n_pins=2)
        new_a, new_b, warnings = add_joints(top, bot, np.zeros(3), np.array([0.,0.,1.]), params)
        assert len(new_a.faces) > 0
        assert len(new_b.faces) > 0


# ── Tipos de conector: pin / ball / dovetail ───────────────────────────────────

class TestTiposDeConector:
    """Sistema de conectores §2.1: os 3 tipos compartilham o mesmo esqueleto
    booleano — macho union na Parte A, fêmea difference na Parte B."""

    def _box_halves(self):
        import trimesh.intersections as ti
        box = trimesh.creation.box(extents=[40., 40., 30.])
        n = np.array([0., 0., 1.])
        top = ti.slice_mesh_plane(box, n, np.zeros(3), cap=True)
        bot = ti.slice_mesh_plane(box, -n, np.zeros(3), cap=True)
        return top, bot

    def _params(self, jt):
        return JointParams(pin_diameter=6.0, pin_depth=8.0, tolerance=0.2,
                           n_pins=1, joint_type=jt)

    @pytest.mark.parametrize("jt", JOINT_TYPES)
    def test_macho_cresce_a_femea_encolhe_b(self, jt):
        top, bot = self._box_halves()
        new_a, new_b, warns = add_joints(
            top, bot, np.zeros(3), np.array([0., 0., 1.]), self._params(jt))
        assert new_a.volume > top.volume, f"macho {jt} não foi criado: {warns}"
        assert new_b.volume < bot.volume, f"cavidade {jt} não foi criada: {warns}"

    @pytest.mark.parametrize("jt", JOINT_TYPES)
    def test_partes_watertight(self, jt):
        top, bot = self._box_halves()
        new_a, new_b, warns = add_joints(
            top, bot, np.zeros(3), np.array([0., 0., 1.]), self._params(jt))
        assert new_a.is_watertight, f"Parte A ({jt}) não watertight: {warns}"
        assert new_b.is_watertight, f"Parte B ({jt}) não watertight: {warns}"

    @pytest.mark.parametrize("jt", JOINT_TYPES)
    def test_folga_macho_cabe_na_femea(self, jt):
        """Assembly fit: toda a superfície exposta do macho (lado B) deve
        estar contida na cavidade fêmea — garante folga ≥ 0 em todo ponto."""
        params = self._params(jt)
        origin, normal = np.zeros(3), np.array([0., 0., 1.])
        males = _male_solids(params, origin, normal)
        females = _female_solids(params, origin, normal)
        pts = np.vstack([m.sample(400) for m in males])
        pts = pts[pts[:, 2] < -0.5]     # ignora a raiz embutida na Parte A
        assert len(pts) > 50
        inside = np.zeros(len(pts), dtype=bool)
        for f in females:
            inside |= f.contains(pts)
        assert inside.all(), f"{int((~inside).sum())} ponto(s) do macho fora da fêmea ({jt})"

    @pytest.mark.parametrize("jt", JOINT_TYPES)
    def test_solidos_base_watertight(self, jt):
        """Pré-requisito das booleanas: cada sólido gerado é manifold fechado."""
        params = self._params(jt)
        for s in _male_solids(params, np.zeros(3), np.array([0., 0., 1.])):
            assert s.is_watertight
        for s in _female_solids(params, np.zeros(3), np.array([0., 0., 1.])):
            assert s.is_watertight

    @pytest.mark.parametrize("normal", [
        [1., 0., 0.], [0., 1., 0.], [0.577, 0.577, 0.577],
    ])
    def test_tipos_novos_normais_arbitrarias(self, normal):
        """Ball e dovetail não podem depender do eixo Z."""
        n = np.array(normal, dtype=float)
        n /= np.linalg.norm(n)
        for jt in ("ball", "dovetail"):
            params = self._params(jt)
            for s in _male_solids(params, np.zeros(3), n) + _female_solids(params, np.zeros(3), n):
                assert s.is_watertight and len(s.faces) > 0

    def test_ball_profundidade_menor_que_raio_nao_crasha(self):
        """Profundidade < raio da esfera: geometria é ajustada, não degenera."""
        params = JointParams(pin_diameter=6.0, pin_depth=1.0, tolerance=0.2,
                             n_pins=1, joint_type="ball")
        for s in _male_solids(params, np.zeros(3), np.array([0., 0., 1.])):
            assert s.is_watertight

    def test_tipo_invalido_levanta_valueerror(self):
        top, bot = self._box_halves()
        with pytest.raises(ValueError):
            add_joints(top, bot, np.zeros(3), np.array([0., 0., 1.]),
                       self._params("parafuso"))


# ── Specs individuais por conector (§2.2) ──────────────────────────────────────

class TestApplyJointSpecs:
    """Cada conector com origem, direção e parâmetros próprios."""

    def _box_halves(self):
        import trimesh.intersections as ti
        box = trimesh.creation.box(extents=[60., 40., 30.])
        n = np.array([0., 0., 1.])
        top = ti.slice_mesh_plane(box, n, np.zeros(3), cap=True)
        bot = ti.slice_mesh_plane(box, -n, np.zeros(3), cap=True)
        return top, bot

    def test_tipos_mistos_no_mesmo_corte(self):
        """Um pino + um dovetail no mesmo corte, tamanhos diferentes."""
        top, bot = self._box_halves()
        z = np.array([0., 0., 1.])
        specs = [
            (np.array([-15., 0., 0.]), z, JointParams(4.0, 6.0, 0.2, 1, "pin")),
            (np.array([15., 0., 0.]), z, JointParams(8.0, 10.0, 0.2, 1, "dovetail")),
        ]
        new_a, new_b, warns = apply_joint_specs(top, bot, specs)
        assert new_a.volume > top.volume, warns
        assert new_b.volume < bot.volume, warns
        assert new_a.is_watertight and new_b.is_watertight, warns

    def test_direcao_inclinada(self):
        """Ângulo da conexão (§2.2): eixo inclinado ~20° da normal do corte."""
        top, bot = self._box_halves()
        d = np.array([0.34, 0., 0.94])
        d /= np.linalg.norm(d)
        specs = [(np.zeros(3), d, JointParams(6.0, 8.0, 0.2, 1, "pin"))]
        new_a, new_b, warns = apply_joint_specs(top, bot, specs)
        assert new_a.volume > top.volume, warns
        assert new_a.is_watertight and new_b.is_watertight, warns

    def test_tipo_invalido_falha_antes_das_booleanas(self):
        top, bot = self._box_halves()
        specs = [
            (np.zeros(3), np.array([0., 0., 1.]), JointParams(6.0, 8.0, 0.2, 1, "pin")),
            (np.zeros(3), np.array([0., 0., 1.]), JointParams(6.0, 8.0, 0.2, 1, "banana")),
        ]
        with pytest.raises(ValueError):
            apply_joint_specs(top, bot, specs)
        # nada foi aplicado (validação vem antes)
        assert len(top.faces) > 0
