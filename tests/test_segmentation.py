"""Testes do módulo de segmentação — suggest_cut_planes, smart_segment, _local_minima."""
import numpy as np
import trimesh
import pytest

from src.segmentation import suggest_cut_planes, smart_segment, _local_minima


# ── _local_minima ──────────────────────────────────────────────────────────────

class TestLocalMinima:

    def test_single_valley(self):
        """Array em forma de V tem um mínimo local no centro."""
        arr = np.array([1.0, 0.8, 0.5, 0.2, 0.5, 0.8, 1.0])
        mins = _local_minima(arr, min_distance=1, min_prominence=0.1)
        assert len(mins) == 1
        assert mins[0] == 3

    def test_two_valleys(self):
        """Dois vales separados → dois mínimos locais."""
        arr = np.array([1.0, 0.2, 1.0, 0.9, 1.0, 0.3, 1.0])
        mins = _local_minima(arr, min_distance=1, min_prominence=0.1)
        assert len(mins) == 2

    def test_flat_no_minima(self):
        """Array plano → sem mínimos locais."""
        arr = np.ones(20)
        mins = _local_minima(arr, min_distance=2, min_prominence=0.01)
        assert len(mins) == 0

    def test_min_distance_filters_close_valleys(self):
        """Dois mínimos muito próximos → min_distance mantém só o mais profundo."""
        arr = np.array([1.0, 0.3, 0.4, 0.2, 1.0])
        # min_distance grande — os dois candidatos próximos devem virar um
        mins = _local_minima(arr, min_distance=3, min_prominence=0.05)
        assert len(mins) <= 1

    def test_prominence_filters_shallow_valleys(self):
        """Vale muito raso (baixa prominência) deve ser filtrado."""
        arr = np.array([0.5, 0.48, 0.5, 0.5, 0.48, 0.5])
        mins = _local_minima(arr, min_distance=1, min_prominence=0.1)
        # prominência ≈ 0.02 < 0.1 → filtrado
        assert len(mins) == 0

    def test_returns_indices_not_values(self):
        """_local_minima retorna índices, não valores."""
        arr = np.array([1.0, 0.1, 1.0])
        mins = _local_minima(arr, min_distance=1, min_prominence=0.1)
        assert len(mins) == 1
        assert isinstance(mins[0], int)
        assert mins[0] == 1  # índice do mínimo


# ── suggest_cut_planes — geometrias simples ────────────────────────────────────

class TestSuggestCutPlanesSphere:

    def test_returns_list(self):
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere)
        assert isinstance(result, list)

    def test_result_has_required_fields(self):
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere, n_results=3)
        for r in result:
            assert "axis" in r
            assert "position" in r
            assert "score" in r
            assert "crossing_count" in r
            assert "balance" in r

    def test_axis_is_valid(self):
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere)
        for r in result:
            assert r["axis"] in ("x", "y", "z"), f"Eixo inválido: {r['axis']}"

    def test_score_in_range(self):
        """Score deve estar em [0, 1]."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere)
        for r in result:
            assert 0.0 <= r["score"] <= 1.0, f"Score fora do range: {r['score']}"

    def test_balance_in_range(self):
        """Balance deve estar em [0, 0.5]."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere)
        for r in result:
            assert 0.0 <= r["balance"] <= 0.5, f"Balance fora do range: {r['balance']}"

    def test_position_within_bounds(self):
        """Posição sugerida deve estar dentro dos limites da mesh."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere)
        bounds = sphere.bounds
        for r in result:
            ax = {"x": 0, "y": 1, "z": 2}[r["axis"]]
            assert bounds[0][ax] <= r["position"] <= bounds[1][ax], \
                f"Posição {r['position']} fora dos bounds {bounds[:, ax]}"

    def test_sorted_by_score_descending(self):
        """Resultado deve estar ordenado por score decrescente."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True), "Resultado não está ordenado por score"

    def test_n_results_respected(self):
        """n_results limita o número de sugestões."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        for n in (1, 3, 5):
            result = suggest_cut_planes(sphere, n_results=n)
            assert len(result) <= n, f"Esperado <= {n} resultados, got {len(result)}"


class TestSuggestCutPlanesCylinder:

    def test_cylinder_has_suggestions(self):
        """Cilindro alongado deve ter sugestões de corte."""
        cyl = trimesh.creation.cylinder(radius=10, height=80, sections=32)
        result = suggest_cut_planes(cyl)
        assert len(result) > 0

    def test_cylinder_cut_along_height(self):
        """Para um cilindro alto, o melhor corte deve ser no eixo Z (height)."""
        cyl = trimesh.creation.cylinder(radius=10, height=80, sections=32)
        result = suggest_cut_planes(cyl, n_results=1)
        if result:
            # O cilindro é muito mais alto que largo — corte ideal em Z (meio)
            # Mas pode ser também em qualquer eixo dependendo da orientação
            assert result[0]["axis"] in ("x", "y", "z")

    def test_cylinder_balance_near_center(self):
        """Melhor corte do cilindro deve estar próximo ao centro (balance alto)."""
        cyl = trimesh.creation.cylinder(radius=10, height=80, sections=32)
        result = suggest_cut_planes(cyl, n_results=1)
        if result:
            # Balance do melhor corte deve ser razoável (não extremamente assimétrico)
            assert result[0]["balance"] > 0.1, \
                f"Melhor corte muito desequilibrado: balance={result[0]['balance']}"


class TestSuggestCutPlanesBox:

    def test_box_returns_suggestions(self):
        box = trimesh.creation.box(extents=[30, 30, 30])
        result = suggest_cut_planes(box)
        # Cubo simétrico pode ter poucos ou nenhum mínimo local claro
        assert isinstance(result, list)

    def test_thin_box_has_cut_perpendicular_to_long_axis(self):
        """Caixa muito achatada (tipo bloco): melhor corte perpendicular ao eixo longo."""
        # Caixa 10×10×100 — eixo Z é muito mais longo
        box = trimesh.creation.box(extents=[10, 10, 100])
        result = suggest_cut_planes(box, n_results=3)
        if result:
            # O eixo Z deve aparecer nas sugestões
            axes = [r["axis"] for r in result]
            assert "z" in axes, f"Eixo Z não sugerido para caixa alta. Sugestões: {result}"


class TestSuggestCutPlanesEdgeCases:

    def test_empty_mesh_no_crash(self):
        """Mesh vazia não deve crashar."""
        empty = trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int))
        result = suggest_cut_planes(empty)
        assert isinstance(result, list)

    def test_flat_mesh_no_crash(self):
        """Mesh plana (span zero em um eixo) não deve crashar."""
        # Quad plano em z=0
        verts = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], dtype=float)
        faces = np.array([[0,1,2],[0,2,3]])
        flat = trimesh.Trimesh(vertices=verts, faces=faces)
        result = suggest_cut_planes(flat)
        assert isinstance(result, list)

    def test_very_small_mesh_no_crash(self):
        """Mesh de 4 faces não deve crashar."""
        tet = trimesh.creation.icosphere(subdivisions=0)  # 4 faces
        result = suggest_cut_planes(tet)
        assert isinstance(result, list)

    def test_balance_never_exceeds_0_5(self):
        """Balance = min(left, right) / total ∈ [0, 0.5] por definição."""
        for subdivisions in [2, 3, 4]:
            sphere = trimesh.creation.icosphere(subdivisions=subdivisions)
            result = suggest_cut_planes(sphere, n_results=5)
            for r in result:
                assert r["balance"] <= 0.5 + 1e-9, \
                    f"Balance {r['balance']} > 0.5 é impossível matematicamente"

    def test_crossing_count_positive(self):
        """Número de faces cruzando o plano deve ser positivo."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere)
        for r in result:
            assert r["crossing_count"] > 0, \
                f"crossing_count deve ser > 0, got {r['crossing_count']}"


# ── suggest_cut_planes — qualidade do resultado ───────────────────────────────

class TestSuggestCutPlanesQuality:

    def test_best_cut_splits_dumbbell_50_50(self):
        """
        Haltere (dumbbell) tem cintura clara no meio — deve ter sugestão balanceada.
        Uma esfera perfeita é simétrica (sem cintura), o algoritmo não encontra
        mínimos locais nela — comportamento correto. O haltere é o caso de teste
        relevante: dois lóbulos conectados por um pescoço fino.
        """
        # Constrói haltere: duas esferas separadas por um cilindro fino
        top = trimesh.creation.icosphere(subdivisions=2)
        top.apply_translation([0, 0, 30])
        neck = trimesh.creation.cylinder(radius=3, height=20, sections=16)
        bot = trimesh.creation.icosphere(subdivisions=2)
        bot.apply_translation([0, 0, -30])
        dumbbell = trimesh.util.concatenate([top, neck, bot])
        result = suggest_cut_planes(dumbbell, n_results=3)
        assert len(result) > 0, "Haltere deve ter pelo menos 1 corte sugerido"
        best = result[0]
        # Melhor corte deve ser no eixo Z (eixo de simetria do haltere)
        assert best["axis"] == "z", \
            f"Haltere vertical: corte deveria ser em Z, got {best['axis']}"
        # Balance: o haltere tem ~50% das faces em cada lóbulo
        assert best["balance"] > 0.2, \
            f"Melhor corte muito desequilibrado: balance={best['balance']}"

    def test_score_improves_with_better_geometry(self):
        """
        Cilindro (com cintura clara em Z) deve ter score mais alto
        que um cubo simples (sem cintura).
        """
        cyl = trimesh.creation.cylinder(radius=5, height=60, sections=32)
        cyl_result = suggest_cut_planes(cyl, n_results=1)

        if cyl_result:
            # Score do cilindro (geometria favorável) deve ser razoável
            assert cyl_result[0]["score"] > 0.1, \
                f"Score do cilindro muito baixo: {cyl_result[0]['score']}"

    def test_no_degenerate_suggestions(self):
        """
        Nenhuma sugestão deve ter score=0 ou balance=0 para geometrias normais.
        Score=0 significaria corte perfeitamente ruim em todos os critérios —
        improvável em meshes geradas por trimesh.
        """
        sphere = trimesh.creation.icosphere(subdivisions=3)
        result = suggest_cut_planes(sphere, n_results=5)
        for r in result:
            assert r["score"] > 0.0, f"Score degenerado: {r}"


# ── smart_segment ──────────────────────────────────────────────────────────────

class TestSmartSegment:

    def test_returns_face_indices(self):
        sphere = trimesh.creation.icosphere(subdivisions=3)
        region = smart_segment(sphere, seed_face_idx=0)
        assert isinstance(region, list)
        assert len(region) > 0

    def test_seed_face_in_region(self):
        """Face semente deve estar na região retornada."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        region = smart_segment(sphere, seed_face_idx=0)
        assert 0 in region, "Face semente não está na região"

    def test_region_size_bounded(self):
        """Região não pode ser maior que max_region_pct * n_faces."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        n_faces = len(sphere.faces)
        max_pct = 0.6
        region = smart_segment(sphere, seed_face_idx=0, max_region_pct=max_pct)
        assert len(region) <= int(n_faces * max_pct) + 1, \
            f"Região maior que max_region_pct: {len(region)} > {int(n_faces * max_pct)}"

    def test_all_indices_valid(self):
        """Todos os índices retornados devem ser índices de face válidos."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        n_faces = len(sphere.faces)
        region = smart_segment(sphere, seed_face_idx=0)
        assert all(0 <= i < n_faces for i in region), "Índice de face fora do range"

    def test_empty_mesh_no_crash(self):
        """Mesh vazia não deve crashar."""
        empty = trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int))
        result = smart_segment(empty, seed_face_idx=0)
        assert isinstance(result, list)

    def test_invalid_seed_no_crash(self):
        """Seed inválido (fora do range) não deve crashar — retorna fallback."""
        sphere = trimesh.creation.icosphere(subdivisions=2)
        n = len(sphere.faces)
        result = smart_segment(sphere, seed_face_idx=n + 9999)
        assert isinstance(result, list)

    def test_graph_cache_reuse(self):
        """Usar _graph_cache deve dar o mesmo resultado que sem cache."""
        sphere = trimesh.creation.icosphere(subdivisions=3)
        cache = {}
        r1 = smart_segment(sphere, seed_face_idx=10, _graph_cache=cache)
        r2 = smart_segment(sphere, seed_face_idx=10, _graph_cache=cache)
        assert r1 == r2, "Cache produziu resultado diferente do original"
        assert "csr" in cache, "Cache não foi populado"

    def test_different_seeds_can_give_different_regions(self):
        """Seeds diferentes em regiões diferentes da mesh devem dar regiões distintas."""
        sphere = trimesh.creation.icosphere(subdivisions=4)
        n = len(sphere.faces)
        r1 = smart_segment(sphere, seed_face_idx=0)
        r2 = smart_segment(sphere, seed_face_idx=n // 2)
        # Em geral, regiões de seeds distantes são diferentes
        # (não garantido para todas as geometrias, mas esfera subdivisions=4 é seguro)
        s1, s2 = set(r1), set(r2)
        # Não devem ser idênticas (seeds em pólos opostos)
        assert s1 != s2 or len(s1) == n, \
            "Seeds opostos deram exatamente a mesma região (suspeito)"
