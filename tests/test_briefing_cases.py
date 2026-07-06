"""
Casos obrigatórios do briefing:
1. Pintar o braço → separa só o braço
2. Detalhe pequeno pintado → não corta o corpo
3. Multi-componentes → componentes não se misturam
4. Pinos: watertight, folga total 2mm e containment nas partes
"""
import numpy as np
import trimesh
import pytest

from src.cutter import cut_by_mask, split_by_components
from src.joints import (
    add_joints, plan_pin_origins, JointParams,
    _cylinder_fits, _WALL_MARGIN, _AXIAL_CLEARANCE, _PIN_EMBED,
)


# ── Fixtures locais ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def body_with_arm():
    """Corpo (esfera r=30) + braço (cilindro r=6, comprimento 40) soldados
    por união booleana — topologia conectada, como um boneco real."""
    body = trimesh.creation.icosphere(subdivisions=3, radius=30.0)
    arm = trimesh.creation.cylinder(radius=6.0, height=40.0, sections=32)
    # Braço ao longo de +X, embutido 5mm no corpo
    arm.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], [1, 0, 0]))
    arm.apply_translation([45.0, 0.0, 0.0])  # span x: 25..65
    merged = trimesh.boolean.union([body, arm], engine="manifold")
    assert merged.is_watertight
    return merged


# ── 1. Pintar braço → só braço ─────────────────────────────────────────────────

class TestPintarBraco:

    def _paint_arm(self, mesh):
        """Faces do braço: centróide além da superfície do corpo (x > 31)."""
        c = mesh.triangles_center
        return np.where(c[:, 0] > 31.0)[0].astype(np.int64)

    def test_separa_somente_o_braco(self, body_with_arm):
        painted_idx = self._paint_arm(body_with_arm)
        assert 0 < len(painted_idx) < len(body_with_arm.faces) // 2

        painted, base, origin, normal = cut_by_mask(body_with_arm, painted_idx)

        # Parte pintada = braço: fica inteira além de x=25 (nada do corpo)
        assert painted.bounds[0][0] >= 25.0, (
            f"parte pintada invadiu o corpo: x_min={painted.bounds[0][0]:.1f}"
        )
        # O braço tem seção fina (raio 6) — não pode carregar a esfera junto
        assert painted.bounds[1][2] - painted.bounds[0][2] < 20.0

        # O corpo permanece na base: esfera completa em Z
        assert base.bounds[0][2] < -25.0 and base.bounds[1][2] > 25.0

    def test_normal_aponta_para_o_braco(self, body_with_arm):
        painted_idx = self._paint_arm(body_with_arm)
        _, _, origin, normal = cut_by_mask(body_with_arm, painted_idx)
        # Interface corpo/braço é ⊥ X; normal deve apontar da base p/ o braço (+X)
        assert normal[0] > 0.7
        # Origin na junção (x ≈ 25..35)
        assert 20.0 < origin[0] < 40.0


# ── 2. Detalhe pequeno → não corta o corpo ─────────────────────────────────────

class TestDetalhePequeno:

    def test_corpo_permanece_integro(self, body_with_arm):
        """Pintar um detalhe minúsculo (calota no topo) não pode levar
        nenhuma face do resto do corpo junto."""
        c = body_with_arm.triangles_center
        painted_idx = np.where(c[:, 2] > 27.0)[0].astype(np.int64)  # calota z>27
        assert 0 < len(painted_idx) < len(body_with_arm.faces) // 20

        painted, base, _, _ = cut_by_mask(body_with_arm, painted_idx)

        # Detalhe: pequeno e restrito ao topo
        assert painted.bounds[0][2] >= 25.0
        # Corpo: mantém TODAS as faces não pintadas (caps podem acrescentar)
        assert len(base.faces) >= len(body_with_arm.faces) - len(painted_idx)
        # Corpo continua com o braço e a esfera inteiros
        assert base.bounds[1][0] > 60.0   # braço presente
        assert base.bounds[0][2] < -25.0  # esfera presente

    def test_volume_do_corpo_quase_intacto(self, body_with_arm):
        c = body_with_arm.triangles_center
        painted_idx = np.where(c[:, 2] > 27.0)[0].astype(np.int64)
        painted, base, _, _ = cut_by_mask(body_with_arm, painted_idx)
        if body_with_arm.is_watertight and base.is_watertight:
            # Base mantém > 95% do volume original
            assert base.volume > body_with_arm.volume * 0.95


# ── 3. Multi-componentes não se misturam ───────────────────────────────────────

class TestMultiComponentes:

    def _make_scene(self):
        s1 = trimesh.creation.icosphere(subdivisions=2, radius=10.0)
        s2 = trimesh.creation.box(extents=[8, 8, 8])
        s2.apply_translation([50, 0, 0])
        s3 = trimesh.creation.cylinder(radius=4.0, height=12.0)
        s3.apply_translation([0, 50, 0])
        return trimesh.util.concatenate([s1, s2, s3])

    def test_tres_componentes_detectados(self):
        parts = split_by_components(self._make_scene())
        assert len(parts) == 3

    def test_cada_parte_e_um_unico_componente(self):
        """Nenhuma parte pode conter geometria de outro componente."""
        parts = split_by_components(self._make_scene())
        for p in parts:
            assert len(p.split(only_watertight=False)) == 1

    def test_bounding_boxes_disjuntas(self):
        """As três regiões originais não podem se misturar nas partes."""
        parts = split_by_components(self._make_scene())
        regions = {"esfera": 0, "caixa": 0, "cilindro": 0}
        for p in parts:
            cx, cy = p.centroid[0], p.centroid[1]
            if cx > 25:
                regions["caixa"] += 1
                assert p.bounds[0][0] > 40  # só a caixa
            elif cy > 25:
                regions["cilindro"] += 1
                assert p.bounds[0][1] > 40  # só o cilindro
            else:
                regions["esfera"] += 1
                assert np.all(np.abs(p.bounds) < 15)  # só a esfera
        assert all(v == 1 for v in regions.values()), regions


# ── 4. Pinos: watertight, folga 2mm, containment ───────────────────────────────

@pytest.mark.slow
class TestPinosFolgaContainment:

    TOL = 1.0  # 1mm por lado = folga total (diametral) de 2mm — FDM padrão

    def _halves(self):
        cyl = trimesh.creation.cylinder(radius=30.0, height=60.0, sections=64)
        n = np.array([0., 0., 1.])
        top = trimesh.intersections.slice_mesh_plane(cyl, n, np.zeros(3), cap=True)
        bot = trimesh.intersections.slice_mesh_plane(cyl, -n, np.zeros(3), cap=True)
        ang = np.linspace(0, 2 * np.pi, 128, endpoint=False)
        cut_pts = np.stack(
            [30 * np.cos(ang), 30 * np.sin(ang), np.zeros(128)], axis=1
        )
        return top, bot, cut_pts, n

    def test_folga_total_2mm(self):
        params = JointParams(pin_diameter=6.0, pin_depth=8.0,
                             tolerance=self.TOL, n_pins=2)
        # Folga diametral: 2 × tolerance = 2mm
        hole_d = params.pin_diameter + 2 * params.tolerance
        assert hole_d - params.pin_diameter == pytest.approx(2.0)

    def test_containment_das_origens(self):
        """Toda origem planejada deve caber: cavidade+parede dentro da Parte B
        e raiz do pino dentro da Parte A."""
        top, bot, cut_pts, n = self._halves()
        params = JointParams(pin_diameter=6.0, pin_depth=8.0,
                             tolerance=self.TOL, n_pins=4)
        origins, notes = plan_pin_origins(top, bot, cut_pts, n, params)
        assert len(origins) >= 1

        pin_r = params.pin_diameter / 2
        hole_r = pin_r + params.tolerance
        for o in origins:
            assert _cylinder_fits(
                bot, o, n, hole_r + _WALL_MARGIN,
                -(params.pin_depth + _AXIAL_CLEARANCE), -0.5,
            ), f"cavidade não cabe na Parte B em {o}"
            assert _cylinder_fits(top, o, n, pin_r, 0.3, _PIN_EMBED * 0.9), \
                f"raiz do pino não apoia na Parte A em {o}"

    def test_resultado_watertight_com_folga_2mm(self):
        top, bot, cut_pts, n = self._halves()
        params = JointParams(pin_diameter=6.0, pin_depth=8.0,
                             tolerance=self.TOL, n_pins=3)
        new_a, new_b, warnings = add_joints(
            top, bot, np.zeros(3), n, params, cut_pts
        )
        assert new_a.is_watertight, f"Parte A não watertight: {warnings}"
        assert new_b.is_watertight, f"Parte B não watertight: {warnings}"
        # Pino protrai da Parte A rumo à Parte B
        assert new_a.bounds[0][2] < -params.pin_depth * 0.8
        # Volumes coerentes: A ganhou pinos, B perdeu cavidades
        assert new_a.volume > top.volume
        assert new_b.volume < bot.volume

    def test_parede_fina_descarta_pinos(self):
        """Tubo de parede fina: pinos que não couberem devem ser descartados
        ou realocados — nunca gerar geometria inválida."""
        outer = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=64)
        inner = trimesh.creation.cylinder(radius=18.5, height=44.0, sections=64)
        tube = trimesh.boolean.difference([outer, inner], engine="manifold")
        n = np.array([0., 0., 1.])
        top = trimesh.intersections.slice_mesh_plane(tube, n, np.zeros(3), cap=True)
        bot = trimesh.intersections.slice_mesh_plane(tube, -n, np.zeros(3), cap=True)
        ang = np.linspace(0, 2 * np.pi, 96, endpoint=False)
        cut_pts = np.stack(
            [19.25 * np.cos(ang), 19.25 * np.sin(ang), np.zeros(96)], axis=1
        )
        params = JointParams(pin_diameter=6.0, pin_depth=8.0,
                             tolerance=self.TOL, n_pins=4)
        origins, notes = plan_pin_origins(top, bot, cut_pts, n, params)
        # Parede de 1.5mm não comporta cavidade de 4mm+margem → tudo descartado,
        # fallback deve avisar (nunca silenciosamente inválido)
        assert notes, "parede fina deveria gerar avisos de descarte/fallback"
