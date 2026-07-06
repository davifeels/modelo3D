import trimesh
import numpy as np
from dataclasses import dataclass

from src import config as cfg
from src import logger as log_mod

_log = log_mod.get()

_JOINT_CFG = cfg.get("joint", "pin_diameter_mm", 3.0), \
             cfg.get("joint", "pin_depth_mm", 8.0), \
             cfg.get("joint", "tolerance_mm", 0.2), \
             cfg.get("joint", "n_pins", 1), \
             cfg.get("joint", "type", "pin")

# Quanto do pino entra na Parte A para a união booleana soldar (mm)
_PIN_EMBED = 2.0
# Folga axial do fundo da cavidade (mm) — o pino não bate no fundo
_AXIAL_CLEARANCE = 1.0
# Parede mínima ao redor da cavidade fêmea (mm)
_WALL_MARGIN = 1.2

# Tipos de conector suportados
JOINT_TYPES = ("pin", "ball", "dovetail")
# Ball joint: raio do pescoço relativo ao raio da esfera (< 1 permite rotação)
_BALL_NECK_RATIO = 0.7
# Dovetail: lado da ponta relativo ao lado da base (plug afunilado pela normal)
_DOVETAIL_TAPER = 0.65


@dataclass
class JointParams:
    pin_diameter: float = _JOINT_CFG[0]   # pin: diâmetro; ball: Ø da esfera; dovetail: lado da base
    pin_depth: float = _JOINT_CFG[1]
    tolerance: float = _JOINT_CFG[2]
    n_pins: int = int(_JOINT_CFG[3])
    joint_type: str = _JOINT_CFG[4]       # "pin" | "ball" | "dovetail"


def _cylinder_transform(direction: np.ndarray, center: np.ndarray) -> np.ndarray:
    direction = direction / np.linalg.norm(direction)
    R = trimesh.geometry.align_vectors(np.array([0.0, 0.0, 1.0]), direction)
    T = np.eye(4)
    T[:3, :3] = R[:3, :3]
    T[:3, 3] = center
    return T


def _make_pin(radius: float, depth: float, origin: np.ndarray, normal: np.ndarray) -> trimesh.Trimesh:
    """
    Pino MACHO. `normal` aponta de part_b → part_a; o pino protrai da face de
    corte da Parte A em direção à Parte B (span [-depth, +_PIN_EMBED] ao longo
    de normal, relativo a origin). A raiz embutida garante que a união solde.
    """
    height = depth + _PIN_EMBED
    pin = trimesh.creation.cylinder(radius=radius, height=height, sections=32)
    center = origin - normal * ((depth - _PIN_EMBED) / 2.0)
    pin.apply_transform(_cylinder_transform(normal, center))
    return pin


def _make_hole(radius: float, depth: float, origin: np.ndarray, normal: np.ndarray) -> trimesh.Trimesh:
    """
    Cavidade FÊMEA na Parte B: mesmo eixo do pino, mais funda
    (_AXIAL_CLEARANCE) e atravessando a face de corte (+1mm) para a
    booleana cortar limpo. Span [-(depth+_AXIAL_CLEARANCE), +1] ao longo de normal.
    """
    over = 1.0
    height = depth + _AXIAL_CLEARANCE + over
    hole = trimesh.creation.cylinder(radius=radius, height=height, sections=32)
    center = origin - normal * ((depth + _AXIAL_CLEARANCE - over) / 2.0)
    hole.apply_transform(_cylinder_transform(normal, center))
    return hole


def _ball_geometry(ball_r: float, depth: float):
    """Profundidade efetiva e offset do centro da esfera (pescoço ≥ 1mm)."""
    depth = max(depth, ball_r + 1.0)
    return depth, depth - ball_r


def _make_ball_male(ball_r: float, depth: float, origin: np.ndarray,
                    normal: np.ndarray) -> list:
    """
    Junta esférica MACHO: pescoço cilíndrico + esfera na ponta. A esfera fica
    do lado da Parte B (span até -depth); o pescoço mais fino que a esfera
    permite leve rotação/ajuste angular na cavidade.
    """
    depth, center_off = _ball_geometry(ball_r, depth)
    ball = trimesh.creation.icosphere(subdivisions=3, radius=ball_r)
    ball.apply_translation(origin - normal * center_off)

    neck = trimesh.creation.cylinder(
        radius=ball_r * _BALL_NECK_RATIO,
        height=center_off + _PIN_EMBED, sections=32,
    )
    neck_center = origin - normal * ((center_off - _PIN_EMBED) / 2.0)
    neck.apply_transform(_cylinder_transform(normal, neck_center))
    return [neck, ball]


def _make_ball_female(ball_r: float, tolerance: float, depth: float,
                      origin: np.ndarray, normal: np.ndarray) -> list:
    """
    Cavidade FÊMEA da junta esférica: esfera (raio + tolerância) + canal de
    entrada do diâmetro do pescoço. Com tolerância pequena o lábio da entrada
    retém a esfera (snap-fit); com folga FDM padrão fica um encaixe livre.
    """
    depth, center_off = _ball_geometry(ball_r, depth)
    over = 1.0
    cavity = trimesh.creation.icosphere(subdivisions=3, radius=ball_r + tolerance)
    cavity.apply_translation(origin - normal * center_off)

    channel = trimesh.creation.cylinder(
        radius=ball_r * _BALL_NECK_RATIO + tolerance,
        height=center_off + over, sections=32,
    )
    channel_center = origin - normal * ((center_off - over) / 2.0)
    channel.apply_transform(_cylinder_transform(normal, channel_center))
    return [cavity, channel]


def _square_corners(side: float, z_off: float, origin: np.ndarray,
                    u: np.ndarray, v: np.ndarray, normal: np.ndarray) -> list:
    h = side / 2.0
    c = origin + normal * z_off
    return [c + u * sx * h + v * sy * h for sx in (-1, 1) for sy in (-1, 1)]


def _make_dovetail_male(width: float, depth: float, origin: np.ndarray,
                        normal: np.ndarray) -> list:
    """
    Dovetail MACHO (plug afunilado pela normal): tronco de pirâmide de seção
    quadrada — base larga na face de corte, ponta estreita. O afunilamento
    auto-centra a montagem e resiste a cisalhamento lateral.
    """
    u, v = _plane_basis(normal)
    pts = (_square_corners(width, _PIN_EMBED, origin, u, v, normal)
           + _square_corners(width * _DOVETAIL_TAPER, -depth, origin, u, v, normal))
    return [trimesh.convex.convex_hull(np.array(pts))]


def _make_dovetail_female(width: float, tolerance: float, depth: float,
                          origin: np.ndarray, normal: np.ndarray) -> list:
    """
    Cavidade FÊMEA do dovetail: mesmo tronco com +tolerância por lado, mais
    fundo (_AXIAL_CLEARANCE) e atravessando a face de corte (+1mm).
    """
    u, v = _plane_basis(normal)
    over = 1.0
    pts = (_square_corners(width + 2 * tolerance, over, origin, u, v, normal)
           + _square_corners(width * _DOVETAIL_TAPER + 2 * tolerance,
                             -(depth + _AXIAL_CLEARANCE), origin, u, v, normal))
    return [trimesh.convex.convex_hull(np.array(pts))]


def _male_solids(params: "JointParams", origin: np.ndarray,
                 normal: np.ndarray) -> list:
    """Sólidos MACHO do conector (para union com a Parte A)."""
    half = params.pin_diameter / 2.0
    if params.joint_type == "pin":
        return [_make_pin(half, params.pin_depth, origin, normal)]
    if params.joint_type == "ball":
        return _make_ball_male(half, params.pin_depth, origin, normal)
    if params.joint_type == "dovetail":
        return _make_dovetail_male(params.pin_diameter, params.pin_depth, origin, normal)
    raise ValueError(f"Tipo de conector desconhecido: {params.joint_type!r}")


def _female_solids(params: "JointParams", origin: np.ndarray,
                   normal: np.ndarray) -> list:
    """Sólidos FÊMEA do conector (para difference da Parte B)."""
    half = params.pin_diameter / 2.0
    if params.joint_type == "pin":
        return [_make_hole(half + params.tolerance, params.pin_depth, origin, normal)]
    if params.joint_type == "ball":
        return _make_ball_female(half, params.tolerance, params.pin_depth, origin, normal)
    if params.joint_type == "dovetail":
        return _make_dovetail_female(params.pin_diameter, params.tolerance,
                                     params.pin_depth, origin, normal)
    raise ValueError(f"Tipo de conector desconhecido: {params.joint_type!r}")


def _female_envelope_radius(params: "JointParams") -> float:
    """Raio do cilindro que circunscreve a fêmea — p/ validação de parede."""
    half = params.pin_diameter / 2.0
    if params.joint_type == "ball":
        return half + params.tolerance
    if params.joint_type == "dovetail":
        return (half + params.tolerance) * float(np.sqrt(2.0))
    return half + params.tolerance


def _male_root_radius(params: "JointParams") -> float:
    """Raio da raiz do macho embutida na Parte A — p/ validação de apoio."""
    half = params.pin_diameter / 2.0
    if params.joint_type == "ball":
        return half * _BALL_NECK_RATIO
    return half


def _plane_basis(normal: np.ndarray):
    """Base ortonormal (u, v) do plano perpendicular a normal."""
    u = np.array([-normal[1], normal[0], 0.0])
    if np.linalg.norm(u) < 1e-6:
        u = np.array([1.0, 0.0, 0.0])
    u = u - u.dot(normal) * normal
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    return u, v


def _order_boundary(pts: np.ndarray, normal: np.ndarray):
    """Ordena pontos da borda por ângulo em torno do centróide no plano ⊥ normal."""
    centroid = pts.mean(axis=0)
    u, v = _plane_basis(normal)
    rel = pts - centroid
    ang = np.arctan2(rel.dot(v), rel.dot(u))
    order = np.argsort(ang)
    return pts[order], ang[order], centroid


def boundary_perimeter(cut_pts: np.ndarray, normal: np.ndarray) -> float:
    """Perímetro aproximado da borda de corte (pontos ordenados por ângulo)."""
    pts = np.asarray(cut_pts, dtype=float)
    if len(pts) < 3:
        return 0.0
    ordered, _, _ = _order_boundary(pts, normal)
    closed = np.vstack([ordered, ordered[:1]])
    return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))


def _offsets_for_n_pins(n: int, cut_section_pts: np.ndarray, normal: np.ndarray) -> list:
    """Distribuição em linha reta através da seção (fallback para bordas pequenas)."""
    if n == 1 or len(cut_section_pts) == 0:
        center = cut_section_pts.mean(axis=0) if len(cut_section_pts) > 0 else np.zeros(3)
        return [center]

    centroid = cut_section_pts.mean(axis=0)

    perp = np.array([-normal[1], normal[2], normal[0]])
    perp -= perp.dot(normal) * normal
    if np.linalg.norm(perp) < 1e-6:
        perp = np.array([normal[2], -normal[0], normal[1]])
        perp -= perp.dot(normal) * normal
    perp /= np.linalg.norm(perp)

    projections = cut_section_pts.dot(perp)
    mn, mx = projections.min(), projections.max()
    span = mx - mn
    mean_proj = projections.mean()

    offsets = []
    for i in range(n):
        t = (i + 1) / (n + 1)
        offsets.append(centroid + perp * (mn + t * span - mean_proj))
    return offsets


def _offsets_along_boundary(n: int, cut_pts: np.ndarray, normal: np.ndarray,
                            inset: float = 0.45) -> list:
    """
    Distribui n pinos uniformemente ao longo da borda de corte, recuados
    `inset` (fração) em direção ao centróide — afasta os pinos da parede.
    """
    pts = np.asarray(cut_pts, dtype=float)
    if n == 1 or len(pts) < 8:
        return _offsets_for_n_pins(n, pts, normal)

    ordered, ang, centroid = _order_boundary(pts, normal)
    targets = -np.pi + (np.arange(n) + 0.5) * (2.0 * np.pi / n)

    origins = []
    for t in targets:
        # menor diferença angular com wrap-around
        diff = np.abs(np.angle(np.exp(1j * (ang - t))))
        p = ordered[int(np.argmin(diff))]
        origins.append(centroid + (p - centroid) * (1.0 - inset))
    return origins


def _cylinder_fits(mesh: trimesh.Trimesh, origin: np.ndarray, normal: np.ndarray,
                   radius: float, span_lo: float, span_hi: float,
                   samples: int = 8) -> bool:
    """
    True se um cilindro (raio `radius`, entre span_lo..span_hi ao longo de
    normal, relativo a origin) cabe inteiramente dentro de `mesh`.
    Amostra o perímetro em 3 profundidades. Sem watertight não há como
    validar com confiança → não bloqueia.
    """
    if not mesh.is_watertight:
        return True
    u, v = _plane_basis(normal)
    angles = np.linspace(0.0, 2.0 * np.pi, samples, endpoint=False)
    ring = np.array([np.cos(a) * u + np.sin(a) * v for a in angles]) * radius

    pts = []
    for f in (0.15, 0.5, 0.85):
        off = span_lo + (span_hi - span_lo) * f
        level = origin + normal * off
        pts.append(ring + level)
        pts.append(level[None, :])
    pts = np.vstack(pts)

    try:
        return bool(mesh.contains(pts).all())
    except Exception:
        return True


def plan_pin_origins(
    mesh_a: trimesh.Trimesh,
    mesh_b: trimesh.Trimesh,
    cut_pts: np.ndarray,
    normal: np.ndarray,
    params: JointParams,
):
    """
    Planeja as posições dos pinos:
    1. candidatos distribuídos ao longo da borda de corte (recuados p/ dentro)
    2. valida espessura de parede: a cavidade (+ margem) deve caber dentro da
       Parte B e a raiz do pino deve estar apoiada em material da Parte A
    3. descarta posições inválidas; se nenhuma sobrar, tenta o centro
    Retorna (origins, notes) — notes são avisos não-fatais para a UI.
    """
    if params.joint_type not in JOINT_TYPES:
        raise ValueError(f"Tipo de conector desconhecido: {params.joint_type!r}")
    normal = normal / np.linalg.norm(normal)
    root_r = _male_root_radius(params)
    envelope_r = _female_envelope_radius(params)
    depth = params.pin_depth
    notes = []

    cut_pts = np.asarray(cut_pts, dtype=float)
    if len(cut_pts) == 0:
        return [np.zeros(3)], ["Borda de corte vazia — pino no origin."]

    def _ok(o):
        socket_ok = _cylinder_fits(
            mesh_b, o, normal, envelope_r + _WALL_MARGIN,
            -(depth + _AXIAL_CLEARANCE), -0.5,
        )
        root_ok = _cylinder_fits(mesh_a, o, normal, root_r, 0.3, _PIN_EMBED * 0.9)
        return socket_ok and root_ok

    candidates = _offsets_along_boundary(params.n_pins, cut_pts, normal)
    valid = [o for o in candidates if _ok(o)]

    if len(valid) < len(candidates):
        notes.append(
            f"{len(candidates) - len(valid)} pino(s) descartado(s) por parede fina."
        )

    if not valid:
        # fallback: centro da seção (linha reta), até 2 pinos
        for o in _offsets_for_n_pins(min(params.n_pins, 2), cut_pts, normal):
            if _ok(o):
                valid.append(o)
        if valid:
            notes.append("Pinos reposicionados para o centro da seção.")

    if not valid:
        valid = [cut_pts.mean(axis=0)]
        notes.append(
            "Não foi possível validar espessura de parede — usando pino único no centro."
        )

    return valid, notes


def add_joints(
    part_a: trimesh.Trimesh,
    part_b: trimesh.Trimesh,
    cut_origin: np.ndarray,
    normal: np.ndarray,
    params: JointParams,
    cut_section_pts: np.ndarray = None,
    origins: list = None,
):
    """
    Adiciona pino(s) MACHO protraindo de part_a e cavidade(s) FÊMEA em part_b.
    normal aponta de part_b → part_a.
    `origins` (opcional) fixa as posições — senão são planejadas com validação
    de espessura de parede (plan_pin_origins).
    Retorna (part_a_modificada, part_b_modificada, lista_de_avisos).
    """
    if params.joint_type not in JOINT_TYPES:
        raise ValueError(f"Tipo de conector desconhecido: {params.joint_type!r}")
    normal = normal / np.linalg.norm(normal)

    _log.info(
        "Adicionando %d conector(es) tipo %s: diâm=%.1f mm, prof=%.1f mm, tol=%.2f mm",
        params.n_pins, params.joint_type,
        params.pin_diameter, params.pin_depth, params.tolerance,
    )

    if cut_section_pts is None or len(cut_section_pts) == 0:
        cut_section_pts = np.array([cut_origin])

    warnings = []
    if origins is None:
        origins, notes = plan_pin_origins(part_a, part_b, cut_section_pts, normal, params)
        warnings.extend(notes)

    result_a = part_a
    result_b = part_b

    for i, origin in enumerate(origins):
        males = _male_solids(params, origin, normal)
        females = _female_solids(params, origin, normal)

        try:
            candidate_a = trimesh.boolean.union([result_a] + males, engine="manifold")
            if candidate_a is not None and len(candidate_a.faces) > 0:
                result_a = candidate_a
                _log.debug("Pino %d adicionado a part_a com sucesso.", i + 1)
            else:
                msg = f"Pino {i+1} produziu mesh vazia; ignorado."
                warnings.append(msg)
                _log.warning(msg)
        except Exception as e:
            msg = f"Pino {i+1} não foi adicionado: {e}"
            warnings.append(msg)
            _log.error("Operação booleana FALHOU — %s", msg, exc_info=True)

        try:
            candidate_b = trimesh.boolean.difference([result_b] + females, engine="manifold")
            if candidate_b is not None and len(candidate_b.faces) > 0:
                result_b = candidate_b
                _log.debug("Furo %d subtraído de part_b com sucesso.", i + 1)
            else:
                msg = f"Furo {i+1} produziu mesh vazia; part_b mantida sem furo."
                warnings.append(msg)
                _log.warning(msg)
        except Exception as e:
            msg = f"Furo {i+1} não foi feito: {e}"
            warnings.append(msg)
            _log.error("Operação booleana FALHOU — %s", msg, exc_info=True)

    if warnings:
        _log.warning("%d aviso(s) durante geração de encaixes.", len(warnings))

    # Verifica watertight após as operações
    if not result_a.is_watertight:
        _log.warning("part_a não é watertight após operações booleanas.")
        warnings.append("Part A não ficou watertight após adicionar pinos.")
    if not result_b.is_watertight:
        _log.warning("part_b não é watertight após operações booleanas.")
        warnings.append("Part B não ficou watertight após adicionar furos.")

    return result_a, result_b, warnings
