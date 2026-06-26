import os
import zipfile
import tempfile
import trimesh


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def export_parts(parts: list, names: list, output_path: str, ext: str = ".stl") -> str:
    """
    Exporta todas as partes como arquivos dentro de um ZIP.
    ext: '.stl' ou '.obj'
    Retorna o caminho do ZIP gerado.
    """
    ext = ext.lower()
    if ext not in (".stl", ".obj"):
        ext = ".stl"

    with tempfile.TemporaryDirectory() as tmp:
        stl_files = []
        for i, (mesh, name) in enumerate(zip(parts, names), start=1):
            safe = _safe_name(name) or f"parte_{i:02d}"
            filepath = os.path.join(tmp, f"{safe}{ext}")
            mesh.export(filepath)
            stl_files.append((filepath, f"{safe}{ext}"))

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for filepath, arcname in stl_files:
                zf.write(filepath, arcname)

    return output_path


def export_single_part(mesh: trimesh.Trimesh, name: str, output_path: str) -> str:
    """
    Exporta uma única parte. Formato determinado pela extensão do output_path.
    Suporta .stl e .obj.
    Retorna o caminho do arquivo gerado.
    """
    mesh.export(output_path)
    return output_path
