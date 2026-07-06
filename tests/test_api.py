"""Testes de integração HTTP — servidor deve estar rodando em localhost:8000."""
import json
import struct
import tempfile
import os
import time
import urllib.request
import urllib.error
import numpy as np
import trimesh
import pytest

BASE = "http://localhost:8000/api"


def _req(method, path, body=None, raw=False):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    rq = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        resp = urllib.request.urlopen(rq, timeout=90)
        raw_bytes = resp.read()
        if raw:
            return raw_bytes, resp.status
        return (json.loads(raw_bytes) if raw_bytes else {}), resp.status
    except urllib.error.HTTPError as e:
        raw_bytes = e.read()
        try:
            return json.loads(raw_bytes), e.code
        except Exception:
            return {"_raw": raw_bytes[:300].decode(errors="replace")}, e.code


def _upload_mesh(mesh) -> str:
    """Faz upload de um trimesh e retorna session_id."""
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        mesh.export(f.name, file_type="stl")
        tmp = f.name
    stl = open(tmp, "rb").read()
    os.unlink(tmp)
    bd = b'Content-Disposition: form-data; name="file"; filename="test.stl"'
    ct = b"Content-Type: application/octet-stream"
    body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + stl + b"\r\n--b--\r\n"
    rq = urllib.request.Request(
        BASE + "/upload", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=b"}
    )
    resp = json.loads(urllib.request.urlopen(rq, timeout=60).read())
    return resp["session_id"]


def _skip_if_no_server():
    try:
        urllib.request.urlopen(BASE + "/session/ping", timeout=2)
    except urllib.error.HTTPError:
        pass  # 404 é ok — servidor está rodando
    except Exception:
        pytest.skip("Servidor não está rodando em localhost:8000")


@pytest.fixture(autouse=True)
def require_server():
    _skip_if_no_server()


# ── Upload ─────────────────────────────────────────────────────────────────────

class TestUpload:

    def test_valid_stl_returns_session(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload_mesh(mesh)
        assert len(sid) > 10

    def test_response_has_info(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            mesh.export(f.name, file_type="stl")
            tmp = f.name
        stl = open(tmp, "rb").read()
        os.unlink(tmp)
        bd = b'Content-Disposition: form-data; name="file"; filename="test.stl"'
        ct = b"Content-Type: application/octet-stream"
        body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + stl + b"\r\n--b--\r\n"
        rq = urllib.request.Request(
            BASE + "/upload", data=body,
            headers={"Content-Type": "multipart/form-data; boundary=b"}
        )
        resp = json.loads(urllib.request.urlopen(rq, timeout=60).read())
        assert "info" in resp
        assert resp["info"]["faces"] > 0

    def test_invalid_file_returns_400(self):
        data = b"isto nao e um stl valido!!!"
        bd = b'Content-Disposition: form-data; name="file"; filename="bad.stl"'
        ct = b"Content-Type: application/octet-stream"
        body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + data + b"\r\n--b--\r\n"
        rq = urllib.request.Request(
            BASE + "/upload", data=body,
            headers={"Content-Type": "multipart/form-data; boundary=b"}
        )
        try:
            urllib.request.urlopen(rq, timeout=10)
            pytest.fail("Deveria ter retornado erro")
        except urllib.error.HTTPError as e:
            assert e.code in (400, 422, 500)

    def test_unsupported_format_returns_400(self):
        data = b"dummy"
        bd = b'Content-Disposition: form-data; name="file"; filename="model.xyz"'
        ct = b"Content-Type: application/octet-stream"
        body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + data + b"\r\n--b--\r\n"
        rq = urllib.request.Request(
            BASE + "/upload", data=body,
            headers={"Content-Type": "multipart/form-data; boundary=b"}
        )
        try:
            urllib.request.urlopen(rq, timeout=10)
            pytest.fail("Deveria ter retornado erro")
        except urllib.error.HTTPError as e:
            assert e.code == 400


# ── Session ────────────────────────────────────────────────────────────────────

class TestSession:

    def test_valid_session_returns_200(self):
        sid = _upload_mesh(trimesh.creation.icosphere(subdivisions=2))
        resp, code = _req("GET", f"/session/{sid}")
        assert code == 200
        assert resp["session_id"] == sid

    def test_invalid_session_returns_404(self):
        _, code = _req("GET", "/session/nao-existe-000")
        assert code == 404

    def test_session_has_parts(self):
        sid = _upload_mesh(trimesh.creation.icosphere(subdivisions=2))
        resp, _ = _req("GET", f"/session/{sid}")
        assert "parts" in resp
        assert len(resp["parts"]) > 0
        assert resp["parts"][0]["face_count"] > 0


# ── mesh-bin ───────────────────────────────────────────────────────────────────

class TestMeshBin:

    def test_returns_binary_with_correct_header(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload_mesh(mesh)
        time.sleep(0.5)  # espera cache
        data, code = _req("GET", f"/mesh-bin/{sid}/0", raw=True)
        assert code == 200
        nv, nf = struct.unpack_from('<II', data, 0)
        assert nv == len(mesh.vertices)
        assert nf == len(mesh.faces)

    def test_invalid_part_idx_returns_422(self):
        sid = _upload_mesh(trimesh.creation.icosphere(subdivisions=2))
        _, code = _req("GET", f"/mesh-bin/{sid}/999")
        assert code == 422

    def test_invalid_session_returns_404(self):
        _, code = _req("GET", "/mesh-bin/nao-existe/0")
        assert code == 404


# ── mesh-adj ───────────────────────────────────────────────────────────────────

class TestMeshAdj:

    def test_returns_adjacency(self):
        sid = _upload_mesh(trimesh.creation.icosphere(subdivisions=2))
        resp, code = _req("GET", f"/mesh-adj/{sid}/0")
        assert code == 200
        assert len(resp["face_adjacency"]) > 0
        assert len(resp["face_adjacency"]) == len(resp["face_adjacency_angles"])


# ── cut-from-painted ───────────────────────────────────────────────────────────

class TestCutFromPainted:

    def _painted_faces(self, mesh):
        centroids = mesh.triangles_center
        return [int(i) for i, c in enumerate(centroids) if c[2] > 0]

    def test_basic_cut(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = self._painted_faces(mesh)
        resp, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        assert code == 200, f"Falhou: {resp.get('_raw', resp)}"
        assert len(resp.get("parts_meta", [])) == 2

    def test_empty_painted_returns_422(self):
        sid = _upload_mesh(trimesh.creation.icosphere(subdivisions=2))
        _, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": [],
        })
        assert code == 422

    def test_cut_returns_origin_and_normal(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = self._painted_faces(mesh)
        resp, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        assert code == 200
        assert len(resp["cut_origin"]) == 3
        assert len(resp["cut_normal"]) == 3
        # Normal deve ser unitário
        n = np.array(resp["cut_normal"])
        assert abs(np.linalg.norm(n) - 1.0) < 0.01

    def test_non_z_cut(self):
        """Corte com faces pintadas no lado X deve funcionar."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        centroids = mesh.triangles_center
        painted = [int(i) for i, c in enumerate(centroids) if c[0] > 0]
        resp, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        assert code == 200
        assert len(resp.get("parts_meta", [])) == 2


# ── Convenção A/B (briefing §2/§6) ─────────────────────────────────────────────

class TestConvencaoParteAB:
    """Regressão da convenção: pintado = Parte B (vermelha, cavidades fêmeas);
    não pintado = Parte A (azul, pinos machos). cut_normal aponta de B para A.
    Sem estes testes a suíte passa mesmo com a convenção invertida."""

    def _cut_top(self):
        """Pinta a calota superior (z > 0) de uma icosfera e corta."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = [int(i) for i, c in enumerate(mesh.triangles_center) if c[2] > 0]
        resp, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        assert code == 200, f"Falhou: {resp.get('_raw', resp)}"
        return resp

    def test_pintado_vira_parte_b(self):
        resp = self._cut_top()
        meta = resp["parts_meta"]
        name_a = meta[resp["part_a_idx"]]["name"]
        name_b = meta[resp["part_b_idx"]]["name"]
        assert name_a.endswith("_base"), f"Parte A deveria ser a base: {name_a}"
        assert name_b.endswith("_pintado"), f"Parte B deveria ser a pintada: {name_b}"

    def test_parte_b_e_a_regiao_pintada(self):
        """Geometria: a calota pintada (z>0) tem que estar na Parte B."""
        resp = self._cut_top()
        meta = resp["parts_meta"]
        bbox_b = meta[resp["part_b_idx"]]["bbox"]
        bbox_a = meta[resp["part_a_idx"]]["bbox"]
        # O importer auto-escala unidades — normaliza pelo raio (polo norte = pintado)
        r = bbox_b["max"][2]
        # Parte B = calota superior: não desce abaixo de z≈0
        assert bbox_b["min"][2] > -0.2 * r, f"Parte B não é a calota pintada: {bbox_b}"
        # Parte A = resto da esfera: alcança o polo sul
        assert bbox_a["min"][2] < -0.8 * r, f"Parte A não é a base: {bbox_a}"

    def test_cut_normal_aponta_de_b_para_a(self):
        """Pintado em cima (B) ⇒ normal B→A aponta para baixo (-z)."""
        resp = self._cut_top()
        n = np.array(resp["cut_normal"])
        assert n[2] < -0.5, f"cut_normal deveria apontar de B (topo) para A (baixo): {n}"

    def test_region_grow_mesma_convencao(self):
        """/region-grow deve seguir a mesma convenção do /cut-from-painted."""
        mesh = trimesh.creation.cylinder(radius=10.0, height=20.0)
        sid = _upload_mesh(mesh)
        resp, code = _req("POST", "/region-grow", {
            "session_id": sid, "part_idx": 0,
            "point": [0.0, 0.0, 10.0],   # centro da tampa superior
            "angle_deg": 30.0,           # para na quina de 90° da borda
        })
        assert code == 200, f"Falhou: {resp.get('_raw', resp)}"
        meta = resp["parts_meta"]
        assert meta[resp["part_a_idx"]]["name"].endswith("_base")
        assert meta[resp["part_b_idx"]]["name"].endswith("_pintado")
        # Tampa pintada em cima ⇒ normal B→A aponta para baixo
        n = np.array(resp["cut_normal"])
        assert n[2] < -0.5, f"cut_normal deveria apontar de B (tampa) para A (corpo): {n}"


# ── preview-joints ─────────────────────────────────────────────────────────────

class TestPreviewJoints:

    def _setup(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = [int(i) for i, c in enumerate(mesh.triangles_center) if c[2] > 0]
        cut_resp, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        return sid, cut_resp

    def test_returns_pins(self):
        sid, cut = self._setup()
        pv, code = _req("POST", "/preview-joints", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        assert code == 200, f"Falhou: {pv}"
        assert pv["n_pins"] > 0
        assert len(pv["pins"]) == pv["n_pins"]

    def test_pin_has_position_and_direction(self):
        sid, cut = self._setup()
        pv, _ = _req("POST", "/preview-joints", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        pin = pv["pins"][0]
        assert len(pin["position"]) == 3
        assert len(pin["direction"]) == 3
        assert pin["pin_radius"] > 0
        assert pin["depth"] > 0

    def test_pin_direction_matches_cut_normal(self):
        sid, cut = self._setup()
        pv, _ = _req("POST", "/preview-joints", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        for pin in pv["pins"]:
            d = np.array(pin["direction"])
            n = np.array(cut["cut_normal"])
            # Direção do pino deve ser paralela à normal de corte
            assert abs(abs(d.dot(n)) - 1.0) < 0.01, f"Pino não alinhado com normal: {d} vs {n}"


# ── Tipos de conector via API ──────────────────────────────────────────────────

class TestJointTypesAPI:
    """joint_type em /preview-joints e /confirm: pin (default), ball, dovetail."""

    def _setup(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = [int(i) for i, c in enumerate(mesh.triangles_center) if c[2] > 0]
        cut_resp, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        return sid, cut_resp

    def _joint_body(self, sid, cut, **extra):
        body = {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        }
        body.update(extra)
        return body

    def test_default_e_pin(self):
        sid, cut = self._setup()
        pv, code = _req("POST", "/preview-joints", self._joint_body(sid, cut))
        assert code == 200, f"Falhou: {pv}"
        assert pv["joint_type"] == "pin"

    def test_preview_dovetail(self):
        sid, cut = self._setup()
        pv, code = _req("POST", "/preview-joints",
                        self._joint_body(sid, cut, joint_type="dovetail"))
        assert code == 200, f"Falhou: {pv}"
        assert pv["joint_type"] == "dovetail"
        assert pv["n_pins"] > 0
        assert all(p["joint_type"] == "dovetail" for p in pv["pins"])

    def test_confirm_ball_gera_partes_watertight(self):
        sid, cut = self._setup()
        resp, code = _req("POST", "/confirm",
                          self._joint_body(sid, cut, joint_type="ball"))
        assert code == 200, f"Falhou: {resp}"
        for m in resp["parts_meta"]:
            assert m["watertight"], f"parte {m['name']} não watertight: {resp['warnings']}"

    def test_confirm_dovetail_gera_partes_watertight(self):
        sid, cut = self._setup()
        resp, code = _req("POST", "/confirm",
                          self._joint_body(sid, cut, joint_type="dovetail"))
        assert code == 200, f"Falhou: {resp}"
        for m in resp["parts_meta"]:
            assert m["watertight"], f"parte {m['name']} não watertight: {resp['warnings']}"

    def test_tipo_invalido_422(self):
        sid, cut = self._setup()
        _, code = _req("POST", "/preview-joints",
                       self._joint_body(sid, cut, joint_type="parafuso"))
        assert code == 422
        _, code = _req("POST", "/confirm",
                       self._joint_body(sid, cut, joint_type="parafuso"))
        assert code == 422

    # ── Assembly fit (flexível / apertado) ──────────────────────────────

    def test_fit_apertado_reduz_tolerancia(self):
        sid, cut = self._setup()
        pv_flex, code = _req("POST", "/preview-joints",
                             self._joint_body(sid, cut, fit="flexivel"))
        assert code == 200, f"Falhou: {pv_flex}"
        pv_tight, code = _req("POST", "/preview-joints",
                              self._joint_body(sid, cut, fit="apertado"))
        assert code == 200, f"Falhou: {pv_tight}"
        assert pv_flex["fit"] == "flexivel" and pv_flex["tolerance"] == 1.0
        assert pv_tight["fit"] == "apertado" and pv_tight["tolerance"] == 0.2

    def test_fit_default_e_flexivel(self):
        sid, cut = self._setup()
        pv, code = _req("POST", "/preview-joints", self._joint_body(sid, cut))
        assert code == 200
        assert pv["fit"] == "flexivel"
        assert pv["tolerance"] == 1.0

    def test_confirm_fit_apertado_watertight(self):
        sid, cut = self._setup()
        resp, code = _req("POST", "/confirm",
                          self._joint_body(sid, cut, joint_type="dovetail", fit="apertado"))
        assert code == 200, f"Falhou: {resp}"
        for m in resp["parts_meta"]:
            assert m["watertight"], f"parte {m['name']} não watertight: {resp['warnings']}"

    def test_fit_invalido_422(self):
        sid, cut = self._setup()
        _, code = _req("POST", "/preview-joints",
                       self._joint_body(sid, cut, fit="banana"))
        assert code == 422


# ── confirm ────────────────────────────────────────────────────────────────────

class TestConfirm:

    def _setup(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = [int(i) for i, c in enumerate(mesh.triangles_center) if c[2] > 0]
        cut, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        return sid, cut

    def test_confirm_returns_200(self):
        sid, cut = self._setup()
        cf, code = _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        assert code == 200, f"Falhou: {cf}"

    def test_confirm_parts_not_empty(self):
        """Bug crítico corrigido: nenhuma parte pode ter 0 faces após confirm."""
        sid, cut = self._setup()
        cf, code = _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        assert code == 200
        for pm in cf.get("parts_meta", []):
            assert pm["face_count"] > 0, f"Parte '{pm.get('name')}' ficou com 0 faces!"

    def test_session_valid_after_confirm(self):
        sid, cut = self._setup()
        _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        # GET /session não pode retornar 500 após confirm
        _, code = _req("GET", f"/session/{sid}")
        assert code == 200, "GET /session retornou erro após confirm"


# ── export ─────────────────────────────────────────────────────────────────────

class TestExport:

    def _confirmed_session(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = [int(i) for i, c in enumerate(mesh.triangles_center) if c[2] > 0]
        cut, _ = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"],
            "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"],
            "cut_normal": cut["cut_normal"],
        })
        return sid

    def test_export_stl_not_empty(self):
        sid = self._confirmed_session()
        data, code = _req("GET", f"/export/{sid}/0/stl", raw=True)
        assert code == 200
        assert len(data) > 84  # header STL = 84 bytes; vazio = exatamente 84

    def test_export_obj(self):
        sid = self._confirmed_session()
        data, code = _req("GET", f"/export/{sid}/0/obj", raw=True)
        assert code == 200
        assert b'v ' in data  # OBJ tem vértices

    def test_export_invalid_session_404(self):
        _, code = _req("GET", "/export/nao-existe/0/stl")
        assert code == 404
