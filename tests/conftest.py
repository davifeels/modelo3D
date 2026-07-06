"""Fixtures compartilhadas entre todos os testes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web', 'backend'))

import pytest
import trimesh
import numpy as np


# ── Geometrias reutilizáveis ───────────────────────────────────────────────────

@pytest.fixture
def sphere():
    """Icosfera com 1280 faces — pequena, rápida."""
    return trimesh.creation.icosphere(subdivisions=3)

@pytest.fixture
def sphere_big():
    """Icosfera com 20480 faces — testa performance."""
    return trimesh.creation.icosphere(subdivisions=5)

@pytest.fixture
def cube():
    return trimesh.creation.box()

@pytest.fixture
def cylinder():
    return trimesh.creation.cylinder(radius=10, height=40, sections=32)

@pytest.fixture
def empty_mesh():
    return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int))

@pytest.fixture
def sphere_halves(sphere):
    """Retorna (top, bottom) de uma esfera cortada em z=0."""
    import trimesh.intersections as ti
    normal = np.array([0., 0., 1.])
    origin = np.zeros(3)
    top = ti.slice_mesh_plane(sphere, normal, origin, cap=True)
    bot = ti.slice_mesh_plane(sphere, -normal, origin, cap=True)
    return top, bot
