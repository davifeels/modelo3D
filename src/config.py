import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

_DEFAULTS = {
    "language": "pt",
    "joint": {
        "pin_diameter_mm": 3.0,
        "pin_depth_mm": 8.0,
        "tolerance_mm": 0.2,
        "n_pins": 1,
    },
    "mesh": {
        "heavy_threshold_faces": 500_000,
        "simplify_target_faces": 200_000,
        "kdtree_sample_size_a": 3000,
        "kdtree_sample_size_b": 2000,
        "boundary_percentile": 10,
    },
    "ui": {
        "explode_factor": 2.5,
        "history_max": 8,
        "default_angle_deg": 30.0,
        "window_width": 1400,
        "window_height": 900,
        "panel_width": 340,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load() -> dict:
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                user = json.load(f)
            return _deep_merge(_DEFAULTS, user)
        except Exception:
            pass
    return dict(_DEFAULTS)


_cfg = _load()


def get(section: str, key: str, default=None):
    return _cfg.get(section, {}).get(key, default)


def get_language() -> str:
    return _cfg.get("language", "pt")


def set_language(lang: str):
    _cfg["language"] = lang
    save()


def save():
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
