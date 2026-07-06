import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import io
import json
import zipfile
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

import session as sess

router = APIRouter(prefix="/api")

FORMATS = {"stl", "obj"}


def _safe_name(name: str, fallback: str = "parte") -> str:
    safe = "".join(c if c.isalnum() or c in "-_ ." else "_" for c in name).strip(" .")
    return safe or fallback


def _content_disposition(filename: str) -> str:
    """
    Headers HTTP são latin-1 — nomes com caracteres fora dele (ex. CJK)
    quebrariam a resposta. RFC 5987: fallback ASCII + filename* em UTF-8.
    """
    ascii_fb = filename.encode("ascii", "replace").decode("ascii").replace('"', "_")
    return f"attachment; filename=\"{ascii_fb}\"; filename*=UTF-8''{quote(filename)}"


@router.get("/export/{session_id}/{part_idx}/{fmt}")
def export_part(session_id: str, part_idx: int, fmt: str, name: Optional[str] = None):
    fmt = fmt.lower().lstrip(".")
    if fmt not in FORMATS:
        raise HTTPException(400, f"Formato inválido: {fmt}. Use stl ou obj.")

    s = _get(session_id)
    if part_idx < 0 or part_idx >= len(s["parts"]):
        raise HTTPException(422, "Índice inválido.")

    mesh = s["parts"][part_idx]
    # Nome editado pelo usuário (query param) tem prioridade sobre o da sessão
    raw_name = name if name else s["names"][part_idx]
    safe = _safe_name(raw_name)

    data = mesh.export(file_type=fmt)
    if isinstance(data, str):
        data = data.encode("utf-8")

    media = "model/stl" if fmt == "stl" else "model/obj"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": _content_disposition(f"{safe}.{fmt}")},
    )


@router.get("/export-zip/{session_id}/{fmt}")
def export_zip(session_id: str, fmt: str, names: Optional[str] = None):
    fmt = fmt.lower().lstrip(".")
    if fmt not in FORMATS:
        raise HTTPException(400, f"Formato inválido: {fmt}. Use stl ou obj.")

    s = _get(session_id)
    if not s["parts"]:
        raise HTTPException(422, "Nenhuma parte para exportar.")

    # names: JSON {"0": "nome_a", "1": "nome_b"} com os nomes editados na UI
    custom = {}
    if names:
        try:
            custom = {int(k): str(v) for k, v in json.loads(names).items()}
        except Exception:
            custom = {}

    buf = io.BytesIO()
    used = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (mesh, name) in enumerate(zip(s["parts"], s["names"])):
            safe = _safe_name(custom.get(i, name), fallback=f"parte_{i+1}")
            # Evita colisão de nomes dentro do ZIP
            final = safe
            k = 2
            while final in used:
                final = f"{safe}_{k}"
                k += 1
            used.add(final)
            data = mesh.export(file_type=fmt)
            if isinstance(data, str):
                data = data.encode("utf-8")
            zf.writestr(f"{final}.{fmt}", data)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="partes_3d.zip"'},
    )


def _get(sid: str) -> dict:
    s = sess.get(sid)
    if not s:
        raise HTTPException(404, "Sessão não encontrada ou expirada.")
    return s
