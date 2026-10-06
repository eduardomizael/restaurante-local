"""Build a Windows release without including local settings or data."""

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(version, revision):
    """Produce the executable bundle, portable installer ZIP and checksum."""
    import re

    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][A-Za-z0-9]+)*", version):
        raise ValueError("Use uma versão como 0.1.0 ou 0.1.0-rc1.")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Informe o SHA completo do commit da release.")
    architecture = "x64" if struct.calcsize("P") == 8 else "x86"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(ROOT / "dist" / architecture),
                    "--workpath", str(ROOT / "build" / f"pyinstaller-{architecture}"),
                    str(ROOT / "packaging" / "restaurante.spec")], cwd=ROOT, check=True)
    stage = ROOT / "build" / f"release-{version}-{architecture}"
    if not stage.resolve().is_relative_to((ROOT / "build").resolve()):
        raise ValueError("Pasta de build fora do projeto.")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    payload = stage / "app"
    shutil.copytree(ROOT / "dist" / architecture / "RestauranteLocal", payload)
    (payload / "version.json").write_text(json.dumps({"version": version, "revision": revision,
                                                      "architecture": architecture}), encoding="utf-8")
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
    for file in ("Atualizar.bat", "Instalar.bat", "Iniciar.bat", "Update.ps1", "Launch.ps1", "Desinstalar.bat", "Uninstall.ps1"):
        source = ROOT / "packaging" / "windows" / file
        if file.endswith(".ps1"):
            # Windows PowerShell 5.1 needs BOM for UTF-8 Portuguese messages.
            (stage / file).write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
        else:
            shutil.copyfile(source, stage / file)
        if file in ("Desinstalar.bat", "Uninstall.ps1"):
            # Older installed updaters only copy the payload and original bootstrap.
            shutil.copyfile(stage / file, payload / file)
    shutil.copyfile(ROOT / "docs" / "DISTRIBUICAO_WINDOWS.md", stage / "LEIA-ME.md")
    archive = ROOT / "dist" / f"RestauranteLocal-windows-{architecture}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                output.write(file, file.relative_to(stage))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "\n", encoding="ascii")
    web_root = ROOT / "dist" / "update-web"
    web = web_root / architecture
    web.mkdir(parents=True, exist_ok=True)
    filename = f"RestauranteLocal-{digest}.zip"
    shutil.copyfile(archive, web / filename)
    manifest = json.dumps({
        "version": version, "revision": revision, "sha256": digest, "package": filename,
        "architecture": architecture,
    }, indent=2)
    (web / "latest.json").write_text(manifest, encoding="utf-8")
    if architecture == "x64":
        # The original x64 installations still query the root manifest.
        (web_root / "latest.json").write_text(manifest, encoding="utf-8")
        shutil.copyfile(archive, web_root / filename)
    (web / "index.html").write_text(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
        '<title>Restaurante Local</title><h1>Restaurante Local</h1>'
        f'<p>Versão {version} — release {revision[:12]}</p>'
        f'<p><a href="{filename}">Baixar pacote Windows {architecture}</a></p>'
        '<p>Extraia o ZIP e execute Instalar.bat. Para atualizar, basta abrir o aplicativo.</p></html>',
        encoding="utf-8",
    )
    (web_root / "index.html").write_text(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
        '<title>Restaurante Local</title><h1>Restaurante Local</h1>'
        '<p>Escolha pelo tipo do Windows instalado, mesmo que o processador seja x64.</p>'
        '<p><a href="x86/">Windows de 32 bits (x86)</a></p>'
        '<p><a href="x64/">Windows de 64 bits (x64)</a></p>'
        '<p>Extraia o ZIP e execute Instalar.bat.</p></html>', encoding="utf-8")
    print(f"Pacote: {archive}\nSHA-256: {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision")
    arguments = parser.parse_args()
    revision = arguments.revision or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    build(arguments.version, revision)
