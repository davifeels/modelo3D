import os
import zipfile
import tempfile
import trimesh


def export_parts(parts: list, names: list, output_path: str) -> str:
    """
    Exporta as partes como STLs dentro de um ZIP.
    Retorna o caminho do ZIP gerado.
    """
    with tempfile.TemporaryDirectory() as tmp:
        stl_files = []
        for mesh, name in zip(parts, names):
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            filepath = os.path.join(tmp, f"{safe_name}.stl")
            mesh.export(filepath)
            stl_files.append((filepath, f"{safe_name}.stl"))

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for filepath, arcname in stl_files:
                zf.write(filepath, arcname)

    return output_path
