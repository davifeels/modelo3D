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

    # ── Edição individual por conector (§2.2) ───────────────────────────

    def test_confirm_com_pins_editados(self):
        """Confirm com overrides individuais: tipos e tamanhos por pino."""
        sid, cut = self._setup()
        pv, _ = _req("POST", "/preview-joints", self._joint_body(sid, cut))
        assert pv["n_pins"] >= 1
        pins = [{
            "position": pv["pins"][0]["position"],
            "joint_type": "dovetail",
            "diameter": pv["pin_diameter"] * 1.5,
            "depth": pv["pin_depth"] * 0.8,
        }]
        resp, code = _req("POST", "/confirm", self._joint_body(sid, cut, pins=pins))
        assert code == 200, f"Falhou: {resp}"
        for m in resp["parts_meta"]:
            assert m["watertight"], f"parte {m['name']}: {resp['warnings']}"

    def test_confirm_pin_com_angulo(self):
        """Direção individual inclinada em relação à normal do corte."""
        sid, cut = self._setup()
        pv, _ = _req("POST", "/preview-joints", self._joint_body(sid, cut))
        n = np.array(cut["cut_normal"], dtype=float)
        tilted = (n + np.array([0.3, 0.0, 0.0]))
        tilted /= np.linalg.norm(tilted)
        pins = [{
            "position": pv["pins"][0]["position"],
            "direction": tilted.tolist(),
        }]
        resp, code = _req("POST", "/confirm", self._joint_body(sid, cut, pins=pins))
        assert code == 200, f"Falhou: {resp}"

    def test_confirm_pins_demais_422(self):
        sid, cut = self._setup()
        pins = [{"position": [0.0, 0.0, 0.0]}] * 13
        _, code = _req("POST", "/confirm", self._joint_body(sid, cut, pins=pins))
        assert code == 422

    def test_confirm_pin_diametro_invalido_422(self):
        sid, cut = self._setup()
        pins = [{"position": [0.0, 0.0, 0.0], "diameter": -2.0}]
        _, code = _req("POST", "/confirm", self._joint_body(sid, cut, pins=pins))
        assert code == 422


# ── Add all connectors: registro multi-interface (§2.3) ───────────────────────

class TestAddAllConnectors:

    def _cut_sphere(self):
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        painted = [int(i) for i, c in enumerate(mesh.triangles_center) if c[2] > 0]
        cut, code = _req("POST", "/cut-from-painted", {
            "session_id": sid, "part_idx": 0,
            "painted_face_indices": painted,
        })
        assert code == 200
        return sid, cut

    def test_interface_registrada_apos_corte(self):
        sid, _ = self._cut_sphere()
        resp, code = _req("GET", f"/interfaces/{sid}")
        assert code == 200
        assert resp["n_pending"] == 1
        itf = resp["pending"][0]
        assert itf["name_a"].endswith("_base") and itf["name_b"].endswith("_pintado")

    def test_confirm_marca_interface_como_feita(self):
        sid, cut = self._cut_sphere()
        _req("POST", "/confirm", {
            "session_id": sid,
            "part_a_idx": cut["part_a_idx"], "part_b_idx": cut["part_b_idx"],
            "cut_origin": cut["cut_origin"], "cut_normal": cut["cut_normal"],
        })
        resp, _ = _req("GET", f"/interfaces/{sid}")
        assert resp["n_pending"] == 0

    def test_confirm_all_processa_todas(self):
        """Dois cortes sem conector → confirm-all gera nos dois de uma vez."""
        sid, cut = self._cut_sphere()
        # Segundo corte: plano no meio da Parte A (idx 0)
        bbox = cut["parts_meta"][0]["bbox"]
        mid_z = (bbox["min"][2] + bbox["max"][2]) / 2
        cut2, code = _req("POST", "/cut", {
            "session_id": sid, "part_idx": 0, "axis": "z", "position": mid_z,
        })
        assert code == 200, f"Falhou: {cut2}"
        resp, _ = _req("GET", f"/interfaces/{sid}")
        assert resp["n_pending"] == 2

        result, code = _req("POST", "/confirm-all", {
            "session_id": sid, "joint_type": "dovetail", "fit": "apertado",
        })
        assert code == 200, f"Falhou: {result}"
        assert result["n_processed"] == 2, f"warnings: {result['warnings']}"
        resp, _ = _req("GET", f"/interfaces/{sid}")
        assert resp["n_pending"] == 0

    def test_confirm_all_sem_pendentes(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload_mesh(mesh)
        result, code = _req("POST", "/confirm-all", {"session_id": sid})
        assert code == 200
        assert result["n_processed"] == 0

    def test_interface_reatribuida_apos_recorte(self):
        """Recortar uma parte migra a interface pendente p/ o filho certo:
        toda interface pendente referencia partes que EXISTEM na sessão."""
        sid, cut = self._cut_sphere()
        bbox = cut["parts_meta"][0]["bbox"]
        mid_z = (bbox["min"][2] + bbox["max"][2]) / 2
        cut2, code = _req("POST", "/cut", {
            "session_id": sid, "part_idx": 0, "axis": "z", "position": mid_z,
        })
        assert code == 200
        current = {m["name"] for m in cut2["parts_meta"]}
        resp, _ = _req("GET", f"/interfaces/{sid}")
        assert resp["n_pending"] == 2  # a antiga migrou + a nova
        for itf in resp["pending"]:
            assert itf["name_a"] in current and itf["name_b"] in current


# ── Máscara multi-peça: /segment-mask, /mask-split, /cut-by-multi-mask (§1) ───

class TestMultiMaskAPI:

    def _upload_cylinder(self):
        mesh = trimesh.creation.cylinder(radius=10.0, height=40.0, sections=32)
        return _upload_mesh(mesh), len(mesh.faces)

    def test_segment_mask_cilindro(self):
        """Cilindro → 3 regiões (tampa/corpo/tampa); labels cobre todas as faces."""
        sid, n_faces = self._upload_cylinder()
        resp, code = _req("POST", "/segment-mask", {
            "session_id": sid, "part_idx": 0, "granularity": "media",
        })
        assert code == 200, f"Falhou: {resp}"
        assert resp["n_regions"] == 3
        assert len(resp["labels"]) == n_faces
        assert sum(resp["region_sizes"].values()) == n_faces

    def test_segment_mask_granularidade_invalida_422(self):
        sid, _ = self._upload_cylinder()
        _, code = _req("POST", "/segment-mask", {
            "session_id": sid, "granularity": "ultra",
        })
        assert code == 422

    def test_cut_by_multi_mask_fluxo_completo(self):
        """segment-mask → cut-by-multi-mask: 3 partes watertight, 2 interfaces
        pendentes, confirm-all processa as duas."""
        sid, _ = self._upload_cylinder()
        seg, _ = _req("POST", "/segment-mask", {"session_id": sid, "granularity": "media"})
        cut, code = _req("POST", "/cut-by-multi-mask", {
            "session_id": sid, "part_idx": 0, "labels": seg["labels"],
        })
        assert code == 200, f"Falhou: {cut}"
        assert cut["n_regions"] == 3
        assert cut["n_interfaces"] == 2
        for m in cut["parts_meta"]:
            assert m["watertight"], f"parte {m['name']} não watertight"

        itf, _ = _req("GET", f"/interfaces/{sid}")
        assert itf["n_pending"] == 2

        result, code = _req("POST", "/confirm-all", {"session_id": sid})
        assert code == 200, f"Falhou: {result}"
        assert result["n_processed"] == 2, f"warnings: {result['warnings']}"

    def test_cut_by_multi_mask_labels_tamanho_errado_422(self):
        sid, _ = self._upload_cylinder()
        _, code = _req("POST", "/cut-by-multi-mask", {
            "session_id": sid, "part_idx": 0, "labels": [0, 1, 0],
        })
        assert code == 422

    def test_mask_split_esfera_sem_quebras_422(self):
        """Esfera lisa não tem quebras internas → split da região falha com 422."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)
        labels = [0] * (len(mesh.faces) // 2) + [1] * (len(mesh.faces) - len(mesh.faces) // 2)
        _, code = _req("POST", "/mask-split", {
            "session_id": sid, "part_idx": 0, "labels": labels, "region_id": 0,
        })
        assert code == 422

    def test_mask_split_superficie_curva_nao_estilhaca_422(self):
        """REGRESSÃO: split da parede lisa do cilindro estilhaçava em ~33
        fatias (Otsu degenerado no ruído de tesselação). Deve dar 422."""
        sid, _ = self._upload_cylinder()
        seg, _ = _req("POST", "/segment-mask", {"session_id": sid, "granularity": "media"})
        # região 0 = maior = parede do cilindro (curva, sem quebras internas)
        resp, code = _req("POST", "/mask-split", {
            "session_id": sid, "part_idx": 0, "labels": seg["labels"], "region_id": 0,
        })
        assert code == 422, f"Split deveria falhar, mas gerou {resp.get('n_regions')} regiões"

    def test_mask_split_com_quebra_real_funciona(self):
        """Região que contém quebra de verdade (caixa fundida no cilindro)
        subdivide em poucas regiões coerentes."""
        cyl = trimesh.creation.cylinder(radius=10.0, height=40.0, sections=32)
        box = trimesh.creation.box(extents=[8.0, 8.0, 20.0])
        box.apply_translation([0, 0, 25.0])
        mesh = trimesh.boolean.union([cyl, box], engine="manifold")
        sid = _upload_mesh(mesh)
        seg, _ = _req("POST", "/segment-mask", {"session_id": sid, "granularity": "baixa"})
        # Pega a região que contém a tampa superior + caixa (tem quebras de 90°)
        labels = np.asarray(seg["labels"])
        n_before = seg["n_regions"]
        # tenta o split em cada região até uma funcionar (a que tem a caixa)
        ok = False
        for rid in range(n_before):
            resp, code = _req("POST", "/mask-split", {
                "session_id": sid, "part_idx": 0,
                "labels": labels.tolist(), "region_id": rid,
            })
            if code == 200:
                ok = True
                assert resp["n_regions"] > n_before
                assert resp["n_regions"] <= n_before + 12, \
                    f"split estilhaçou: {resp['n_regions']} regiões"
                break
        assert ok, "nenhuma região aceitou split (esperava a região com a caixa)"

    def test_segment_mask_apos_corte_usa_malha_atual(self):
        """REGRESSÃO (cache de grafo obsoleto): após um corte, os índices das
        partes deslocam mas o cache _seg_graph_ da sessão era mantido — a
        segmentação devolvia labels da malha ANTIGA (tamanho errado)."""
        sid, _ = self._upload_cylinder()
        # Força a construção do cache de grafo da parte 0 (malha original)
        _req("POST", "/segment-mask", {"session_id": sid, "granularity": "media"})
        # Corta → parte 0 agora é outra malha, com outro nº de faces
        cut, code = _req("POST", "/cut", {
            "session_id": sid, "part_idx": 0, "axis": "z", "position": 0.0,
        })
        assert code == 200, f"Falhou: {cut}"
        n_faces_a = cut["parts_meta"][0]["face_count"]
        resp, code = _req("POST", "/segment-mask", {
            "session_id": sid, "part_idx": 0, "granularity": "media",
        })
        assert code == 200, f"Falhou: {resp}"
        assert len(resp["labels"]) == n_faces_a, (
            f"labels tem {len(resp['labels'])} entradas; parte 0 tem {n_faces_a} faces "
            "— segmentação usou grafo obsoleto de outra malha."
        )


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
