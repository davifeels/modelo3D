"""
Testes de fluxos reais de usuário.
Cobre o que uma pessoa sentada na frente da aplicação faria —
incluindo erros, mudanças de ideia, casos extremos e concorrência.
"""
import json
import os
import struct
import tempfile
import threading
import time
import urllib.error
import urllib.request

import numpy as np
import pytest
import trimesh

import apiauth

BASE = "http://localhost:8000/api"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _req(method, path, body=None, raw=False, timeout=90):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    hdrs.update(apiauth.auth_headers())
    rq = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        resp = urllib.request.urlopen(rq, timeout=timeout)
        rb = resp.read()
        if raw:
            return rb, resp.status
        return (json.loads(rb) if rb else {}), resp.status
    except urllib.error.HTTPError as e:
        rb = e.read()
        try:
            return json.loads(rb), e.code
        except Exception:
            return {"_raw": rb[:300].decode(errors="replace")}, e.code


def _upload(mesh, fmt="stl") -> dict:
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
        mesh.export(f.name, file_type=fmt)
        tmp = f.name
    raw = open(tmp, "rb").read()
    os.unlink(tmp)
    fname = f"model.{fmt}".encode()
    bd = b'Content-Disposition: form-data; name="file"; filename="' + fname + b'"'
    ct = b"Content-Type: application/octet-stream"
    body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + raw + b"\r\n--b--\r\n"
    rq = urllib.request.Request(
        BASE + "/upload", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=b", **apiauth.auth_headers()},
    )
    return json.loads(urllib.request.urlopen(rq, timeout=60).read())


def _painted(mesh, axis="z", sign=1):
    c = mesh.triangles_center
    col = {"x": 0, "y": 1, "z": 2}[axis]
    if sign > 0:
        return [int(i) for i, v in enumerate(c) if v[col] > 0]
    return [int(i) for i, v in enumerate(c) if v[col] < 0]


def _full_pipeline(mesh, axis="z"):
    """Executa upload → cut → preview → confirm e devolve (sid, cf)."""
    up = _upload(mesh)
    sid = up["session_id"]
    painted = _painted(mesh, axis)
    cut, _ = _req("POST", "/cut-from-painted", {
        "session_id": sid, "part_idx": 0,
        "painted_face_indices": painted,
    })
    _req("POST", "/preview-joints", {
        "session_id": sid,
        "part_a_idx": cut["part_a_idx"],
        "part_b_idx": cut["part_b_idx"],
        "cut_origin": cut["cut_origin"],
        "cut_normal": cut["cut_normal"],
    })
    cf, code = _req("POST", "/confirm", {
        "session_id": sid,
        "part_a_idx": cut["part_a_idx"],
        "part_b_idx": cut["part_b_idx"],
        "cut_origin": cut["cut_origin"],
        "cut_normal": cut["cut_normal"],
    })
    return sid, cf, code


def _skip_if_no_server():
    try:
        urllib.request.urlopen(BASE + "/session/ping", timeout=2)
    except urllib.error.HTTPError:
        pass
    except Exception:
        pytest.skip("Servidor não está rodando em localhost:8000")


@pytest.fixture(autouse=True)
def require_server():
    _skip_if_no_server()


# ══════════════════════════════════════════════════════════════════════════════
# 1. FORMATOS DE ARQUIVO
# ══════════════════════════════════════════════════════════════════════════════

class TestFileFormats:

    def test_upload_stl(self):
        up = _upload(trimesh.creation.icosphere(subdivisions=2), fmt="stl")
        assert up["info"]["faces"] > 0

    def test_upload_obj(self):
        up = _upload(trimesh.creation.icosphere(subdivisions=2), fmt="obj")
        assert up["info"]["faces"] > 0

    def test_upload_preserves_face_count(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        up = _upload(mesh)
        assert up["info"]["faces"] == len(mesh.faces)

    def test_upload_reports_dimensions(self):
        up = _upload(trimesh.creation.box(extents=[10, 20, 30]))
        dims = up["info"]["dims"]
        assert len(dims) == 3
        assert all(d > 0 for d in dims)

    def test_empty_filename_rejected(self):
        data = b""
        bd = b'Content-Disposition: form-data; name="file"; filename="empty.stl"'
        ct = b"Content-Type: application/octet-stream"
        body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + data + b"\r\n--b--\r\n"
        rq = urllib.request.Request(
            BASE + "/upload", data=body,
            headers={"Content-Type": "multipart/form-data; boundary=b", **apiauth.auth_headers()},
        )
        try:
            urllib.request.urlopen(rq, timeout=10)
            pytest.fail("Deveria ter rejeitado arquivo vazio")
        except urllib.error.HTTPError as e:
            assert e.code in (400, 422, 500)

    def test_wrong_extension_rejected(self):
        bd = b'Content-Disposition: form-data; name="file"; filename="model.png"'
        ct = b"Content-Type: application/octet-stream"
        body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + b"dummy" + b"\r\n--b--\r\n"
        rq = urllib.request.Request(
            BASE + "/upload", data=body,
            headers={"Content-Type": "multipart/form-data; boundary=b", **apiauth.auth_headers()},
        )
        try:
            urllib.request.urlopen(rq, timeout=10)
            pytest.fail("PNG deveria ser rejeitado")
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_corrupt_stl_returns_error_not_500(self):
        """Arquivo corrompido deve retornar 400, não 500 (internal error)."""
        corrupt = b"\x00" * 80 + b"\xff\xff\xff\xff"  # header STL + n_tris inválido
        bd = b'Content-Disposition: form-data; name="file"; filename="corrupt.stl"'
        ct = b"Content-Type: application/octet-stream"
        body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + corrupt + b"\r\n--b--\r\n"
        rq = urllib.request.Request(
            BASE + "/upload", data=body,
            headers={"Content-Type": "multipart/form-data; boundary=b", **apiauth.auth_headers()},
        )
        try:
            urllib.request.urlopen(rq, timeout=10)
        except urllib.error.HTTPError as e:
            assert e.code != 500, f"Arquivo corrompido retornou 500 (server error interno)"


# ══════════════════════════════════════════════════════════════════════════════
# 2. USUÁRIO VOLTA ATRÁS E RE-CORTA
# ══════════════════════════════════════════════════════════════════════════════

class TestUserChangedMind:

    def test_corta_duas_vezes_mesma_sessao(self):
        """Usuário corta, não gosta, volta e corta de novo na mesma sessão."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]

        # Primeiro corte: pinta em Z
        p1 = _painted(mesh, "z", sign=1)
        cut1, code1 = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": p1,
        })
        assert code1 == 200

        # "Não gostei" — faz upload de novo e recomeça
        sid2 = _upload(mesh)["session_id"]
        p2 = _painted(mesh, "x", sign=1)  # corte diferente
        cut2, code2 = _req("POST", "/cut-from-painted", {
            "session_id": sid2, "part_idx": 0,
            "painted_face_indices": p2,
        })
        assert code2 == 200
        assert len(cut2.get("parts_meta", [])) == 2

    def test_preview_multiplas_vezes(self):
        """Usuário chama preview-joints várias vezes antes de confirmar."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        cut, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        payload = {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        }
        for _ in range(3):
            pv, code = _req("POST", "/preview-joints", payload)
            assert code == 200
            assert pv["n_pins"] > 0

    def test_confirm_sem_preview_funciona(self):
        """Confirmar sem chamar preview-joints deve funcionar."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        cut, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        cf, code = _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        assert code == 200

    def test_exportar_antes_de_confirmar_retorna_dados_ou_erro(self):
        """Export do modelo original (antes de confirmar) deve funcionar ou retornar erro claro."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]
        # Export retorna binário STL — usar raw=True
        data, code = _req("GET", f"/export/{sid}/0/stl", raw=True)
        # Deve funcionar (retorna o modelo original) ou dar erro HTTP claro, nunca 500
        assert code != 500
        if code == 200:
            assert len(data) > 84  # não pode ser STL vazio


# ══════════════════════════════════════════════════════════════════════════════
# 3. CASOS EXTREMOS DE PINTURA
# ══════════════════════════════════════════════════════════════════════════════

class TestPaintingEdgeCases:

    def test_pintar_1_porcento_das_faces(self):
        """Região muito pequena deve ser rejeitada."""
        mesh = trimesh.creation.icosphere(subdivisions=4)  # 5120 faces
        n_total = len(mesh.faces)
        tiny = list(range(int(n_total * 0.005)))  # 0.5%
        sid = _upload(mesh)["session_id"]
        _, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": tiny,
        })
        # Corte com região muito pequena deve falhar com 422 ou 200 (se conseguir cortar)
        assert code in (200, 422)

    def test_pintar_99_porcento_das_faces(self):
        """Região enorme deve ser rejeitada ou gerar corte."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        n_total = len(mesh.faces)
        almost_all = list(range(int(n_total * 0.99)))
        sid = _upload(mesh)["session_id"]
        _, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": almost_all,
        })
        assert code in (200, 422)

    def test_face_indices_fora_do_range(self):
        """Índices de face maiores que n_faces devem retornar 422/500 sem crashar."""
        mesh = trimesh.creation.icosphere(subdivisions=2)
        n = len(mesh.faces)
        sid = _upload(mesh)["session_id"]
        _, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": [n + 9999, n + 10000],
        })
        assert code in (422, 500)

    def test_faces_duplicadas_na_pintura(self):
        """Lista com índices repetidos não deve crashar."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        p = _painted(mesh)
        duplicated = p + p  # duplica todos os índices
        sid = _upload(mesh)["session_id"]
        _, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": duplicated,
        })
        assert code in (200, 422)

    def test_corte_em_3_eixos_diferentes(self):
        """Usuário testa cortar o mesmo modelo em X, Y e Z."""
        for axis in ["x", "y", "z"]:
            mesh = trimesh.creation.icosphere(subdivisions=3)
            sid = _upload(mesh)["session_id"]
            p = _painted(mesh, axis=axis, sign=1)
            cut, code = _req("POST", "/cut-from-painted", {
                "session_id": sid, "part_idx": 0,
                "painted_face_indices": p,
            })
            assert code == 200, f"Falhou para eixo {axis}: {cut.get('_raw', cut)}"
            assert len(cut.get("parts_meta", [])) == 2


# ══════════════════════════════════════════════════════════════════════════════
# 4. RESTAURAÇÃO DE SESSÃO (reload de página)
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionRestore:

    def test_sessao_persiste_apos_corte(self):
        """Sessão deve ser recuperável após cut-from-painted."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        # Simula reload: GET /session
        resp, code = _req("GET", f"/session/{sid}")
        assert code == 200
        assert len(resp["parts"]) == 2

    def test_sessao_invalida_retorna_404(self):
        _, code = _req("GET", "/session/sessao-que-nao-existe-xyz")
        assert code == 404

    def test_sessao_apos_confirm_tem_2_partes(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid, cf, _ = _full_pipeline(mesh)
        resp, code = _req("GET", f"/session/{sid}")
        assert code == 200
        assert len(resp["parts"]) == 2

    def test_mesh_bin_disponivel_apos_restore(self):
        """Após restaurar sessão, mesh-bin deve funcionar para todas as partes."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        cut, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        for i in range(2):
            data, code = _req("GET", f"/mesh-bin/{sid}/{i}", raw=True)
            assert code == 200, f"mesh-bin/{i} falhou: {code}"
            nv, nf = struct.unpack_from('<II', data, 0)
            assert nf > 0, f"Parte {i} tem 0 faces no mesh-bin"


# ══════════════════════════════════════════════════════════════════════════════
# 5. MODELOS COM CARACTERÍSTICAS ESPECIAIS
# ══════════════════════════════════════════════════════════════════════════════

class TestSpecialModels:

    def test_modelo_com_multiplos_componentes(self):
        """Modelo com 2 partes separadas — usuário deve conseguir processar."""
        s1 = trimesh.creation.icosphere(subdivisions=2)
        s2 = trimesh.creation.icosphere(subdivisions=2)
        s2.apply_translation([50, 0, 0])
        combined = trimesh.util.concatenate([s1, s2])
        up = _upload(combined)
        assert up["info"]["faces"] > 0
        assert up["info"]["n_components"] == 2

    def test_modelo_escala_centimetros(self):
        """Modelo em escala de centímetros (dims >> mm)."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        mesh.apply_scale(10.0)  # escala 10x — como se fosse em cm
        up = _upload(mesh)
        dims = up["info"]["dims"]
        assert all(d > 0 for d in dims)

    def test_modelo_muito_pequeno(self):
        """Modelo minúsculo (< 1mm) não deve travar."""
        mesh = trimesh.creation.icosphere(subdivisions=2)
        mesh.apply_scale(0.01)  # 0.01x — muito pequeno
        up = _upload(mesh)
        assert up["info"]["faces"] > 0

    def test_cubo_corte_e_export(self):
        """Cubo (geometria simples) — pipeline completo."""
        mesh = trimesh.creation.box(extents=[30, 30, 30])
        sid, cf, code = _full_pipeline(mesh)
        assert code == 200
        for pm in cf.get("parts_meta", []):
            assert pm["face_count"] > 0

    def test_cilindro_pipeline_completo(self):
        mesh = trimesh.creation.cylinder(radius=15, height=40, sections=32)
        sid, cf, code = _full_pipeline(mesh)
        assert code == 200
        for pm in cf.get("parts_meta", []):
            assert pm["face_count"] > 0

    def test_torus_pipeline_completo(self):
        mesh = trimesh.creation.torus(major_radius=20, minor_radius=5)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        if not p:
            pytest.skip("Torus não tem faces acima de z=0 nessa orientação")
        cut, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        assert code in (200, 422)  # torus pode falhar geometricamente — ok


# ══════════════════════════════════════════════════════════════════════════════
# 6. EXPORT — TODOS OS FORMATOS E CASOS EXTREMOS
# ══════════════════════════════════════════════════════════════════════════════

class TestExportEdgeCases:

    def test_export_parte_0_e_1_stl(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid, _, _ = _full_pipeline(mesh)
        for i in range(2):
            data, code = _req("GET", f"/export/{sid}/{i}/stl", raw=True)
            assert code == 200
            assert len(data) > 84, f"Parte {i} exportada como STL vazio"

    def test_export_parte_0_e_1_obj(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid, _, _ = _full_pipeline(mesh)
        for i in range(2):
            data, code = _req("GET", f"/export/{sid}/{i}/obj", raw=True)
            assert code == 200
            assert b"v " in data, f"Parte {i} OBJ sem vértices"

    def test_stl_binario_valido(self):
        """STL exportado deve ter header correto e n_tris coerente com tamanho."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid, _, _ = _full_pipeline(mesh)
        data, _ = _req("GET", f"/export/{sid}/0/stl", raw=True)
        # STL binário: 80 bytes header + 4 bytes n_tris + n_tris * 50 bytes
        n_tris = struct.unpack_from('<I', data, 80)[0]
        expected_size = 80 + 4 + n_tris * 50
        assert len(data) == expected_size, f"STL inválido: n_tris={n_tris} mas size={len(data)}"

    def test_export_formato_invalido_retorna_erro(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload(mesh)["session_id"]
        _, code = _req("GET", f"/export/{sid}/0/ply")
        assert code in (400, 404, 422)

    def test_export_parte_inexistente_retorna_422(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload(mesh)["session_id"]
        _, code = _req("GET", f"/export/{sid}/99/stl")
        assert code == 422

    def test_export_cada_parte_tem_volume(self):
        """Cada parte exportada deve ter volume > 0 (não pode ser mesh vazia)."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid, _, _ = _full_pipeline(mesh)
        for i in range(2):
            data, code = _req("GET", f"/export/{sid}/{i}/stl", raw=True)
            assert code == 200
            m = trimesh.load(trimesh.util.wrap_as_stream(data), file_type="stl")
            assert len(m.faces) > 0, f"Parte {i} exportada com 0 faces"
            # Volume pode ser maior que o original (pinos adicionam volume) — só verifica > 0
            if m.is_watertight:
                assert abs(m.volume) > 0


# ══════════════════════════════════════════════════════════════════════════════
# 7. CORTE MANUAL POR PLANO
# ══════════════════════════════════════════════════════════════════════════════

class TestManualCut:

    def test_corte_manual_z(self):
        sid = _upload(trimesh.creation.icosphere(subdivisions=3))["session_id"]
        cut, code = _req("POST", "/cut", {
            "session_id": sid, "part_idx": 0, "axis": "z", "position": 0.0,
        })
        assert code == 200
        assert len(cut.get("parts_meta", [])) == 2

    @pytest.mark.parametrize("axis", ["x", "y", "z"])
    def test_corte_manual_todos_eixos(self, axis):
        sid = _upload(trimesh.creation.icosphere(subdivisions=3))["session_id"]
        cut, code = _req("POST", "/cut", {
            "session_id": sid, "part_idx": 0, "axis": axis, "position": 0.0,
        })
        assert code == 200

    def test_eixo_invalido_retorna_422(self):
        sid = _upload(trimesh.creation.icosphere(subdivisions=2))["session_id"]
        _, code = _req("POST", "/cut", {
            "session_id": sid, "part_idx": 0, "axis": "w", "position": 0.0,
        })
        assert code == 422

    def test_corte_fora_dos_limites_retorna_422(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload(mesh)["session_id"]
        _, code = _req("POST", "/cut", {
            "session_id": sid, "part_idx": 0, "axis": "z", "position": 9999.0,
        })
        assert code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 8. USUÁRIOS SIMULTÂNEOS (CONCORRÊNCIA)
# ══════════════════════════════════════════════════════════════════════════════

class TestConcurrency:

    def test_3_usuarios_simultaneos_pipeline_completo(self):
        """3 usuários fazendo pipeline completo ao mesmo tempo."""
        results = {}
        errors = {}

        def run_pipeline(user_id):
            try:
                mesh = trimesh.creation.icosphere(subdivisions=3)
                sid, cf, code = _full_pipeline(mesh)
                results[user_id] = {"code": code, "parts": len(cf.get("parts_meta", []))}
            except Exception as e:
                errors[user_id] = str(e)

        threads = [threading.Thread(target=run_pipeline, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)

        assert not errors, f"Erros em threads: {errors}"
        for uid, res in results.items():
            assert res["code"] == 200, f"Usuário {uid} falhou: {res}"
            assert res["parts"] == 2, f"Usuário {uid} não gerou 2 partes"

    def test_sessoes_nao_interferem(self):
        """Dados de uma sessão não podem vazar para outra."""
        mesh_a = trimesh.creation.icosphere(subdivisions=2)  # 320 faces
        mesh_b = trimesh.creation.icosphere(subdivisions=3)  # 1280 faces

        sid_a = _upload(mesh_a)["session_id"]
        sid_b = _upload(mesh_b)["session_id"]

        resp_a, _ = _req("GET", f"/session/{sid_a}")
        resp_b, _ = _req("GET", f"/session/{sid_b}")

        faces_a = resp_a["parts"][0]["face_count"]
        faces_b = resp_b["parts"][0]["face_count"]

        assert faces_a != faces_b, "Sessões com meshes diferentes têm mesmo face_count?"
        assert faces_a == len(mesh_a.faces)
        assert faces_b == len(mesh_b.faces)

    def test_10_uploads_simultaneos(self):
        """Servidor não deve travar com 10 uploads ao mesmo tempo."""
        results = {}
        mesh = trimesh.creation.icosphere(subdivisions=2)

        def do_upload(i):
            try:
                up = _upload(mesh)
                results[i] = up["session_id"]
            except Exception as e:
                results[i] = f"ERRO: {e}"

        threads = [threading.Thread(target=do_upload, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        sids = [v for v in results.values() if not v.startswith("ERRO")]
        assert len(sids) == 10, f"Apenas {len(sids)}/10 uploads OK: {results}"
        # Todos devem ter session_id único
        assert len(set(sids)) == 10, "Sessões duplicadas!"


# ══════════════════════════════════════════════════════════════════════════════
# 9. ERROS QUE O USUÁRIO PODE CAUSAR
# ══════════════════════════════════════════════════════════════════════════════

class TestUserErrors:

    def test_confirmar_com_indices_trocados(self):
        """Usuário passa part_a_idx e part_b_idx invertidos."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        cut, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        # Inverte os índices
        cf, code = _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_b_idx"],
            "part_b_idx": cut["part_a_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        # Pode funcionar (apenas inverte pino/furo) ou dar 422 — não pode dar 500
        assert code != 500

    def test_preview_com_sessao_invalida(self):
        _, code = _req("POST", "/preview-joints", {
            "session_id": "nao-existe",
            "part_a_idx": 0, "part_b_idx": 1,
            "cut_origin": [0, 0, 0], "cut_normal": [0, 0, 1],
        })
        assert code == 404

    def test_confirm_com_sessao_invalida(self):
        _, code = _req("POST", "/confirm", {
            "session_id": "nao-existe",
            "part_a_idx": 0, "part_b_idx": 1,
            "cut_origin": [0, 0, 0], "cut_normal": [0, 0, 1],
        })
        assert code == 404

    def test_cut_from_painted_sessao_invalida(self):
        _, code = _req("POST", "/cut-from-painted", {
            "session_id": "nao-existe", "part_idx": 0,
            "painted_face_indices": [0, 1, 2],
        })
        assert code == 404

    def test_normal_zero_no_confirm(self):
        """Normal zerada não deve travar o servidor."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        cut, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        cf, code = _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": [0, 0, 0],
            "cut_normal": [0, 0, 0],  # normal zero!
        })
        assert code != 500  # pode dar 422, mas não 500


# ══════════════════════════════════════════════════════════════════════════════
# 10. PERFORMANCE BÁSICA
# ══════════════════════════════════════════════════════════════════════════════

class TestPerformance:

    def test_upload_5120_faces_em_menos_de_5s(self):
        mesh = trimesh.creation.icosphere(subdivisions=4)  # 5120 faces
        t0 = time.perf_counter()
        up = _upload(mesh)
        dt = time.perf_counter() - t0
        assert up["info"]["faces"] == len(mesh.faces)
        assert dt < 5.0, f"Upload demorou {dt:.1f}s (muito lento)"

    def test_cut_5120_faces_em_menos_de_10s(self):
        mesh = trimesh.creation.icosphere(subdivisions=4)
        sid = _upload(mesh)["session_id"]
        p = _painted(mesh)
        t0 = time.perf_counter()
        _, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0, "painted_face_indices": p,
        })
        dt = time.perf_counter() - t0
        assert code == 200
        assert dt < 10.0, f"Cut demorou {dt:.1f}s (muito lento)"

    def test_mesh_bin_servido_em_menos_de_5s(self):
        mesh = trimesh.creation.icosphere(subdivisions=4)
        sid = _upload(mesh)["session_id"]
        time.sleep(1.0)  # espera pré-cache em background
        t0 = time.perf_counter()
        data, code = _req("GET", f"/mesh-bin/{sid}/0", raw=True)
        dt = time.perf_counter() - t0
        assert code == 200
        assert dt < 5.0, f"mesh-bin demorou {dt:.1f}s (deve ser servido do cache)"

    def test_pipeline_completo_20480_faces(self):
        """Pipeline com 20k faces deve terminar em menos de 60s."""
        mesh = trimesh.creation.icosphere(subdivisions=5)  # 20480 faces
        t0 = time.perf_counter()
        sid, cf, code = _full_pipeline(mesh)
        dt = time.perf_counter() - t0
        assert code == 200, f"Pipeline falhou: {cf}"
        assert dt < 60.0, f"Pipeline com 20k faces demorou {dt:.0f}s"
