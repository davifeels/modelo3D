"""Testes da camada de sessão — serialização binária, adjacência, cache."""
import struct
import numpy as np
import trimesh
import pytest

import session as sess


# ── mesh_to_binary ─────────────────────────────────────────────────────────────

class TestMeshToBinary:

    def _decode(self, data):
        nv, nf = struct.unpack_from('<II', data, 0)
        return nv, nf

    def test_normal_sphere(self, sphere):
        sid = sess.create()
        data = sess.mesh_to_binary(sid, 0, sphere)
        nv, nf = self._decode(data)
        assert nv == len(sphere.vertices)
        assert nf == len(sphere.faces)
        assert len(data) > 8

    def test_empty_mesh_no_crash(self, empty_mesh):
        """mesh vazia não deve lançar exceção."""
        sid = sess.create()
        data = sess.mesh_to_binary(sid, 0, empty_mesh)
        nv, nf = self._decode(data)
        assert nv == 0
        assert nf == 0

    def test_cache_hit(self, sphere):
        """Segunda chamada deve retornar os mesmos bytes (cache)."""
        sid = sess.create()
        b1 = sess.mesh_to_binary(sid, 0, sphere)
        b2 = sess.mesh_to_binary(sid, 0, sphere)
        assert b1 is b2  # mesmo objeto = cache funcionou

    def test_cache_invalidated_on_update(self, sphere, cube):
        """Cache deve ser invalidado quando parts é atualizado."""
        sid = sess.create()
        sess.update(sid, parts=[sphere], names=['sphere'])
        b1 = sess.mesh_to_binary(sid, 0, sphere)
        sess.update(sid, parts=[cube], names=['cube'])
        b2 = sess.mesh_to_binary(sid, 0, cube)
        assert b1 is not b2

    def test_binary_size_reasonable(self, sphere):
        """Tamanho binário deve ser << JSON equivalente."""
        import json
        sid = sess.create()
        data = sess.mesh_to_binary(sid, 0, sphere)
        json_size = len(json.dumps({
            'v': sphere.vertices.tolist(),
            'f': sphere.faces.tolist(),
        }).encode())
        assert len(data) < json_size * 0.7  # pelo menos 30% menor

    def test_cube_no_crash(self, cube):
        sid = sess.create()
        data = sess.mesh_to_binary(sid, 0, cube)
        nv, nf = self._decode(data)
        assert nv > 0 and nf > 0


# ── mesh_adjacency ─────────────────────────────────────────────────────────────

class TestMeshAdjacency:

    def test_returns_adjacency_and_angles(self, sphere):
        sid = sess.create()
        result = sess.mesh_adjacency(sid, 0, sphere)
        assert 'face_adjacency' in result
        assert 'face_adjacency_angles' in result
        assert len(result['face_adjacency']) == len(result['face_adjacency_angles'])
        assert len(result['face_adjacency']) > 0

    def test_cache_hit(self, sphere):
        sid = sess.create()
        r1 = sess.mesh_adjacency(sid, 0, sphere)
        r2 = sess.mesh_adjacency(sid, 0, sphere)
        assert r1 is r2

    def test_angles_in_radians_range(self, sphere):
        sid = sess.create()
        result = sess.mesh_adjacency(sid, 0, sphere)
        angles = np.array(result['face_adjacency_angles'])
        assert angles.min() >= 0
        assert angles.max() <= np.pi + 1e-6


# ── mesh_to_dict ───────────────────────────────────────────────────────────────

class TestMeshToDict:

    def test_empty_mesh_no_crash(self, empty_mesh):
        result = sess.mesh_to_dict(empty_mesh, 'empty')
        assert result['face_count'] == 0
        assert result['bbox'] == {'min': [0,0,0], 'max': [0,0,0]}

    def test_sphere_fields(self, sphere):
        result = sess.mesh_to_dict(sphere, 'sphere')
        assert result['face_count'] == len(sphere.faces)
        assert result['vertex_count'] == len(sphere.vertices)
        assert 'bbox' in result
        assert 'center' in result

    def test_watertight_sphere_has_volume(self, sphere):
        result = sess.mesh_to_dict(sphere, 'sphere')
        assert result['is_watertight']
        assert result['volume_cm3'] is not None
        assert result['volume_cm3'] > 0


# ── session CRUD ───────────────────────────────────────────────────────────────

class TestSessionCRUD:

    def test_create_and_get(self):
        sid = sess.create()
        s = sess.get(sid)
        assert s is not None
        assert 'parts' in s

    def test_get_invalid_returns_none(self):
        assert sess.get('nao-existe-000') is None

    def test_update(self, sphere):
        sid = sess.create()
        sess.update(sid, parts=[sphere], names=['s'])
        s = sess.get(sid)
        assert len(s['parts']) == 1

    def test_delete(self):
        sid = sess.create()
        sess.delete(sid)
        assert sess.get(sid) is None
