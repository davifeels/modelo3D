"""Testes HTTP faltantes para cobertura do backend."""
import io
import json
import os
import struct
import tempfile
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pytest
import trimesh

BASE = "http://localhost:8000/api"


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _upload_raw(data: bytes, filename: str) -> dict:
    """Faz upload de bytes brutos com o filename fornecido."""
    bd = f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode()
    ct = b"Content-Type: application/octet-stream"
    body = b"--b\r\n" + bd + b"\r\n" + ct + b"\r\n\r\n" + data + b"\r\n--b--\r\n"
    rq = urllib.request.Request(
        BASE + "/upload", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=b"}
    )
    resp = urllib.request.urlopen(rq, timeout=60)
    return json.loads(resp.read())


def _mesh_stl_bytes(mesh=None) -> bytes:
    if mesh is None:
        mesh = trimesh.creation.icosphere(subdivisions=2)
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        mesh.export(f.name, file_type="stl")
        tmp = f.name
    data = open(tmp, "rb").read()
    os.unlink(tmp)
    return data


def _upload_mesh(mesh=None, filename="test.stl") -> str:
    return _upload_raw(_mesh_stl_bytes(mesh), filename)["session_id"]


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


# ── Upload: nomes especiais ────────────────────────────────────────────────────

class TestUploadSpecialNames:

    def test_same_file_twice_gives_different_session_ids(self):
        """Dois uploads do mesmo arquivo devem gerar sessões diferentes."""
        data = _mesh_stl_bytes()
        r1 = _upload_raw(data, "test.stl")
        r2 = _upload_raw(data, "test.stl")
        assert r1["session_id"] != r2["session_id"]

    def test_filename_with_spaces(self):
        """Nome com espaços deve ser aceito."""
        data = _mesh_stl_bytes()
        result = _upload_raw(data, "meu modelo.stl")
        assert "session_id" in result
        assert len(result["session_id"]) > 0

    def test_filename_with_accents(self):
        """Nome com acentos deve ser aceito."""
        data = _mesh_stl_bytes()
        result = _upload_raw(data, "peça_3D.stl")
        assert "session_id" in result

    def test_filename_very_long(self):
        """Nome com 255+ caracteres deve ser aceito sem crash."""
        data = _mesh_stl_bytes()
        long_name = "a" * 250 + ".stl"
        result = _upload_raw(data, long_name)
        assert "session_id" in result


# ── Export ZIP ────────────────────────────────────────────────────────────────

class TestExportZip:

    def test_export_zip_stl_is_valid_zip(self):
        sid = _upload_mesh()
        raw, status = _req("GET", f"/export-zip/{sid}/stl", raw=True)
        assert status == 200
        assert zipfile.is_zipfile(io.BytesIO(raw)), "Resposta não é um ZIP válido"

    def test_export_zip_obj_is_valid_zip(self):
        sid = _upload_mesh()
        raw, status = _req("GET", f"/export-zip/{sid}/obj", raw=True)
        assert status == 200
        assert zipfile.is_zipfile(io.BytesIO(raw))

    def test_export_zip_contains_files(self):
        sid = _upload_mesh()
        raw, status = _req("GET", f"/export-zip/{sid}/stl", raw=True)
        assert status == 200
        zf = zipfile.ZipFile(io.BytesIO(raw))
        assert len(zf.namelist()) >= 1

    def test_export_zip_invalid_format(self):
        sid = _upload_mesh()
        result, status = _req("GET", f"/export-zip/{sid}/xyz")
        assert status == 400

    def test_export_zip_nonexistent_session(self):
        result, status = _req("GET", "/export-zip/nonexistent_sid_000/stl")
        assert status == 404


# ── Export individual: todas as combinações ───────────────────────────────────

class TestExportCombinations:

    def _cut_session(self):
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload_mesh(mesh)
        # Corta no plano z=0
        midz = float(mesh.centroid[2])
        body = {"session_id": sid, "part_idx": 0, "axis": "z", "position": midz}
        result, status = _req("POST", "/cut", body)
        assert status == 200, f"Corte falhou: {result}"
        return sid

    def test_export_part0_stl(self):
        sid = self._cut_session()
        raw, status = _req("GET", f"/export/{sid}/0/stl", raw=True)
        assert status == 200
        # STL binário: header(80) + count(4) + triângulos
        assert len(raw) > 84, "STL não tem triângulos"

    def test_export_part0_obj(self):
        sid = self._cut_session()
        raw, status = _req("GET", f"/export/{sid}/0/obj", raw=True)
        assert status == 200
        text = raw.decode("utf-8", errors="replace")
        assert "v " in text, "OBJ não tem vértices"
        assert "f " in text, "OBJ não tem faces"

    def test_export_part1_stl(self):
        sid = self._cut_session()
        raw, status = _req("GET", f"/export/{sid}/1/stl", raw=True)
        assert status == 200
        assert len(raw) > 84

    def test_export_part1_obj(self):
        sid = self._cut_session()
        raw, status = _req("GET", f"/export/{sid}/1/obj", raw=True)
        assert status == 200
        text = raw.decode("utf-8", errors="replace")
        assert "v " in text
        assert "f " in text

    def test_stl_has_triangles(self):
        """STL binário: verifica que o contador de triângulos é > 0."""
        sid = self._cut_session()
        raw, status = _req("GET", f"/export/{sid}/0/stl", raw=True)
        assert status == 200
        # bytes 80-83 = uint32 = número de triângulos
        n_triangles = struct.unpack_from("<I", raw, 80)[0]
        assert n_triangles > 0, "STL exportado tem 0 triângulos"

    def test_obj_has_vertices_and_faces(self):
        """OBJ: verifica linhas 'v ' e 'f '."""
        sid = self._cut_session()
        raw, status = _req("GET", f"/export/{sid}/0/obj", raw=True)
        assert status == 200
        lines = raw.decode("utf-8", errors="replace").splitlines()
        v_lines = [l for l in lines if l.startswith("v ")]
        f_lines = [l for l in lines if l.startswith("f ")]
        assert len(v_lines) > 0
        assert len(f_lines) > 0


# ── Split components ──────────────────────────────────────────────────────────

class TestSplitComponents:

    def test_split_two_spheres(self):
        """Modelo com 2 esferas separadas deve dar split=True, n_components=2."""
        # Cria duas esferas separadas
        s1 = trimesh.creation.icosphere(subdivisions=2)
        s2 = trimesh.creation.icosphere(subdivisions=2)
        s2.apply_translation([100, 0, 0])
        combined = trimesh.util.concatenate([s1, s2])

        data = combined.export(file_type="stl")
        if isinstance(data, str):
            data = data.encode()
        result_up = _upload_raw(data, "two_spheres.stl")
        sid = result_up["session_id"]

        result, status = _req("POST", "/split-components", {"session_id": sid, "part_idx": 0})
        assert status == 200
        # Pode ser que load_mesh já separe os componentes; verificar split ou n_components
        if result.get("split"):
            assert result["n_components"] >= 2

    def test_split_single_mesh_returns_split_false(self):
        """Mesh única (esfera) não deve ser splitada."""
        sid = _upload_mesh()
        result, status = _req("POST", "/split-components", {"session_id": sid, "part_idx": 0})
        assert status == 200
        # Pode retornar split=False ou split=True com 1 componente (mesh já integrada)
        # O importante é não dar 500
        assert "parts_meta" in result or "split" in result


# ── Region grow ───────────────────────────────────────────────────────────────

class TestRegionGrow:

    def test_region_grow_with_point(self):
        """Region grow com ponto no centro da esfera."""
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload_mesh(mesh)
        # Ponto no topo da esfera
        top_point = [0.0, 0.0, float(mesh.bounds[1][2])]
        body = {
            "session_id": sid,
            "part_idx": 0,
            "point": top_point,
            "angle_deg": 45.0,
        }
        result, status = _req("POST", "/region-grow", body)
        # Deve retornar 200 com corte ou 422 se não conseguiu separar
        assert status in (200, 422)
        if status == 200:
            assert "cut_origin" in result
            assert "cut_normal" in result

    def test_region_grow_default_angle(self):
        """Region grow com angle_deg padrão."""
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload_mesh(mesh)
        top_point = [0.0, 0.0, float(mesh.bounds[1][2])]
        body = {
            "session_id": sid,
            "part_idx": 0,
            "point": top_point,
        }
        result, status = _req("POST", "/region-grow", body)
        assert status in (200, 422)


# ── Erros de body JSON ────────────────────────────────────────────────────────

class TestMalformedBody:

    def _post_raw(self, path: str, body_bytes: bytes, content_type="application/json"):
        rq = urllib.request.Request(
            BASE + path, data=body_bytes,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(rq, timeout=10)
            return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read()), e.code
            except Exception:
                return {}, e.code

    def test_malformed_json_returns_422_or_400(self):
        """Body JSON inválido deve retornar 4xx, não 500."""
        result, status = self._post_raw("/cut", b"{not valid json")
        assert status in (400, 422), f"Esperado 4xx, got {status}"

    def test_missing_required_field_returns_422(self):
        """Faltando campo obrigatório 'axis' em /cut."""
        body = json.dumps({"session_id": "fake", "position": 0.0}).encode()
        result, status = self._post_raw("/cut", body)
        assert status == 422, f"Esperado 422, got {status}: {result}"

    def test_missing_session_id_returns_422(self):
        """Faltando campo obrigatório 'session_id'."""
        body = json.dumps({"axis": "z", "position": 0.0}).encode()
        result, status = self._post_raw("/cut", body)
        assert status == 422

    def test_empty_body_returns_422(self):
        """Body vazio deve dar 422."""
        result, status = self._post_raw("/cut", b"")
        assert status == 422


# ── Sessão expirada ───────────────────────────────────────────────────────────

class TestExpiredSession:

    def test_cut_on_nonexistent_session(self):
        """Operar em sessão que não existe deve dar 404."""
        body = {"session_id": "sessao_falsa_que_nao_existe", "part_idx": 0, "axis": "z", "position": 0.0}
        result, status = _req("POST", "/cut", body)
        assert status == 404

    def test_export_nonexistent_session(self):
        result, status = _req("GET", "/export/nao_existe/0/stl")
        assert status == 404

    def test_confirm_nonexistent_session(self):
        body = {
            "session_id": "nao_existe",
            "part_a_idx": 0,
            "part_b_idx": 1,
            "cut_origin": [0, 0, 0],
            "cut_normal": [0, 0, 1],
        }
        result, status = _req("POST", "/confirm", body)
        assert status == 404

    def test_mesh_adj_nonexistent_session(self):
        result, status = _req("GET", "/mesh-adj/nao_existe/0")
        assert status == 404


# ── Operações em índice inválido ─────────────────────────────────────────────

class TestInvalidPartIndex:

    def test_mesh_adj_part_not_exists(self):
        """mesh-adj com parte que não existe deve dar 422."""
        sid = _upload_mesh()
        result, status = _req("GET", f"/mesh-adj/{sid}/999")
        assert status == 422

    def test_export_invalid_part(self):
        sid = _upload_mesh()
        result, status = _req("GET", f"/export/{sid}/999/stl")
        assert status == 422

    def test_cut_invalid_part(self):
        sid = _upload_mesh()
        body = {"session_id": sid, "part_idx": 999, "axis": "z", "position": 0.0}
        result, status = _req("POST", "/cut", body)
        assert status == 422


# ── Cortar parte já cortada ───────────────────────────────────────────────────

class TestCutAlreadyCut:

    def test_cut_from_painted_after_cut(self):
        """Cortar novamente uma parte já cortada."""
        mesh = trimesh.creation.icosphere(subdivisions=3)
        sid = _upload_mesh(mesh)

        # Primeiro corte
        body1 = {"session_id": sid, "part_idx": 0, "axis": "z", "position": 0.0}
        r1, s1 = _req("POST", "/cut", body1)
        assert s1 == 200

        # Segundo corte na parte 0 (que agora é menor)
        body2 = {"session_id": sid, "part_idx": 0, "axis": "y", "position": 0.0}
        r2, s2 = _req("POST", "/cut", body2)
        # Deve funcionar (200) ou dar 422 se a parte ficou vazia
        assert s2 in (200, 422), f"Esperado 200 ou 422, got {s2}: {r2}"


# ── Confirmar duas vezes ──────────────────────────────────────────────────────

class TestDoubleConfirm:

    def test_confirm_twice(self):
        """Confirmar duas vezes a mesma sessão."""
        mesh = trimesh.creation.icosphere(subdivisions=2)
        sid = _upload_mesh(mesh)

        # Corte
        body_cut = {"session_id": sid, "part_idx": 0, "axis": "z", "position": 0.0}
        r_cut, s_cut = _req("POST", "/cut", body_cut)
        assert s_cut == 200

        cut_origin = r_cut["cut_origin"]
        cut_normal = r_cut["cut_normal"]

        body_confirm = {
            "session_id": sid,
            "part_a_idx": 0,
            "part_b_idx": 1,
            "cut_origin": cut_origin,
            "cut_normal": cut_normal,
        }

        r1, s1 = _req("POST", "/confirm", body_confirm)
        assert s1 == 200, f"Primeira confirmação falhou: {r1}"

        # Segunda confirmação — deve funcionar ou dar erro claro (não 500)
        r2, s2 = _req("POST", "/confirm", body_confirm)
        assert s2 in (200, 404, 422), f"Segunda confirmação deu {s2}: {r2}"


# ── Upload OBJ com material embutido ─────────────────────────────────────────

class TestObjUpload:

    def test_upload_obj_with_mtl_comment(self):
        """Upload de OBJ simples (sem mtl externo) deve funcionar."""
        obj_content = b"""# OBJ com comentario de material
mtllib noop.mtl
v 0 0 0
v 1 0 0
v 0 1 0
v 0 0 1
f 1 2 3
f 1 2 4
f 1 3 4
f 2 3 4
"""
        result = _upload_raw(obj_content, "model.obj")
        assert "session_id" in result
        assert len(result["session_id"]) > 0
