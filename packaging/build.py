"""Build a Windows release without including local settings or data."""

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(version, revision):
    """Produce the executable bundle, portable installer ZIP and checksum."""
    import re

    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)*", version):
        raise ValueError("Use uma versão como 0.1.0 ou 0.1.0-rc1.")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Informe o SHA completo do commit da main.")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    str(ROOT / "packaging" / "restaurante.spec")], cwd=ROOT, check=True)
    stage = ROOT / "build" / f"release-{version}"
    stage.mkdir(parents=True, exist_ok=True)
    payload = stage / "app"
    shutil.copytree(ROOT / "dist" / "RestauranteLocal", payload, dirs_exist_ok=True)
    (payload / "version.json").write_text(json.dumps({"version": version, "revision": revision}), encoding="utf-8")
    licenses = payload / "licenses"
    licenses.mkdir(exist_ok=True)
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        destination = licenses / name
        destination.mkdir(exist_ok=True)
        for file in distribution.files or []:
            if "license" in str(file).lower() or "copying" in str(file).lower():
                source = distribution.locate_file(file)
                if source.is_file():
                    shutil.copyfile(source, destination / Path(file).name)
    for file in ("Atualizar.bat", "Instalar.bat", "Iniciar.bat", "Update.ps1", "Launch.ps1"):
        source = ROOT / "packaging" / "windows" / file
        if file.endswith(".ps1"):
            # Windows PowerShell 5.1 needs BOM for UTF-8 Portuguese messages.
            (stage / file).write_text(source.read_text(encoding="utf-8"), encoding="utf-8-sig")
        else:
            shutil.copyfile(source, stage / file)
    shutil.copyfile(ROOT / "docs" / "DISTRIBUICAO_WINDOWS.md", stage / "LEIA-ME.md")
    archive = ROOT / "dist" / "RestauranteLocal-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                output.write(file, file.relative_to(stage))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "\n", encoding="ascii")
    web = ROOT / "dist" / "update-web"
    web.mkdir(exist_ok=True)
    filename = f"RestauranteLocal-{digest}.zip"
    shutil.copyfile(archive, web / filename)
    (web / "latest.json").write_text(json.dumps({
        "version": version, "revision": revision, "sha256": digest, "package": filename,
    }, indent=2), encoding="utf-8")
    (web / "index.html").write_text(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
        '<title>Restaurante Local</title><h1>Restaurante Local</h1>'
        f'<p>Versão {version} — main {revision[:12]}</p>'
        f'<p><a href="{filename}">Baixar pacote Windows x64</a></p>'
        '<p>Extraia o ZIP e execute Instalar.bat. Para atualizar, basta abrir o aplicativo.</p></html>',
        encoding="utf-8",
    )
    print(f"Pacote: {archive}\nSHA-256: {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision")
    arguments = parser.parse_args()
    revision = arguments.revision or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    build(arguments.version, revision)
