"""Prepare immutable Git installations; invoked only by the locked updater."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


DEFAULT_REPOSITORY = "https://github.com/eduardomizael/restaurante-local.git"
TOOLS = ("Launch.ps1", "Update.ps1", "Update-Source.ps1", "Iniciar.bat",
         "Atualizar.bat", "Desinstalar.bat", "Uninstall.ps1")


class ToolFailure(RuntimeError):
    """Keep the native exit code for the active-instance preflight."""

    def __init__(self, executable, returncode):
        self.returncode = returncode
        super().__init__(f"{Path(executable).name}: falha com código {returncode}.")


def write_record(path, record):
    """Replace a JSON record atomically within its directory."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_record(path):
    """Read both Python JSON and Windows PowerShell UTF-8 BOM records."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def command(arguments, *, cwd, timeout=120, capture=False):
    """Run a noninteractive tool with controlled project environment."""
    environment = dict(os.environ)
    for name in ("UV_PROJECT_ENVIRONMENT", "UV_PYTHON", "VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never",
                       DJANGO_SETTINGS_MODULE="config.settings")
    result = subprocess.run([str(item) for item in arguments], cwd=cwd, env=environment,
                            timeout=timeout, capture_output=capture, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        # Avoid echoing URLs/credentials from native tool failures.
        raise ToolFailure(arguments[0], result.returncode)
    return result.stdout.strip() if capture else None


def active_directory(root, record):
    """Constrain the pointer to one owned version directory."""
    if not re.fullmatch(r"versions/[a-f0-9]{64}", record.get("directory", "")):
        raise ValueError("Registro de versão inválido.")
    directory = root / record["directory"]
    if directory.resolve().parent != (root / "versions").resolve():
        raise ValueError("Versão fora da instalação.")
    return directory


def maintenance(directory, record, action, *, capture=False):
    """Use the installed interpreter directly, without uv or hardware."""
    if record.get("mode") == "source":
        arguments = [directory / ".venv/Scripts/python.exe", directory / "manage.py", action]
    else:
        arguments = [directory / "Manutencao.exe", action]
    return command(arguments, cwd=directory, capture=capture)


def update(root, repository=None, *, check_on_start=False):
    """Update code and data while the PowerShell parent owns update.lock.

    Args:
        root: Installation directory, separate from the data directory.
        repository: Git URL for initial installation or explicit channel change.
        check_on_start: Reopen an active instance without attempting an update.
    """
    root = root.resolve()
    pointer = root / "current.json"
    marker = root / "update-failed.txt"
    current = read_record(pointer) if pointer.exists() else None
    if current:
        directory = active_directory(root, current)
        try:
            maintenance(directory, current, "check_update_allowed")
        except ToolFailure as error:
            if check_on_start and error.returncode == 2:
                return
            raise
    channel = root / "source-settings.json"
    settings = read_record(channel) if channel.exists() else {}
    repository = repository or settings.get("repository", DEFAULT_REPOSITORY)
    if not isinstance(repository, str) or not repository or repository.startswith("-"):
        raise ValueError("Repositório inválido.")
    revision_line = command(["git", "ls-remote", "--exit-code", repository, "refs/heads/main"],
                            cwd=root, timeout=15, capture=True)
    revision = revision_line.split()[0] if revision_line else ""
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("A main não informou um commit válido.")
    if (current and current.get("mode") == "source" and current.get("revision") == revision
            and not marker.exists()):
        write_record(channel, {"repository": repository, "branch": "main"})
        print("A versão da main já está instalada.")
        return
    digest = hashlib.sha256(revision.encode("ascii")).hexdigest()
    candidate = root / "versions" / digest
    candidate.parent.mkdir(exist_ok=True)
    if candidate.exists():
        if candidate.is_symlink() or candidate.resolve().parent != candidate.parent.resolve():
            raise ValueError("Pasta de versão inválida.")
        try:
            actual = command(["git", "rev-parse", "HEAD"], cwd=candidate, capture=True)
        except ToolFailure:
            # A interrupted fetch can be retried only in this updater's owned snapshot.
            ownership = candidate / "source-candidate.json"
            if not ownership.exists() or read_record(ownership).get("revision") != revision:
                raise ValueError("Pasta incompleta sem identificação. Confira os logs.") from None
            command(["git", "fetch", "--depth=1", "origin", revision], cwd=candidate)
            command(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=candidate)
            actual = command(["git", "rev-parse", "HEAD"], cwd=candidate, capture=True)
        if actual != revision:
            raise ValueError("Versão incompleta. Confira a pasta informada nos logs antes de tentar novamente.")
        if command(["git", "status", "--porcelain", "--untracked-files=no"], cwd=candidate, capture=True):
            raise ValueError("Código instalado foi alterado localmente. Atualização cancelada.")
    else:
        candidate.mkdir()
        write_record(candidate / "source-candidate.json", {"revision": revision})
        command(["git", "init", "--quiet"], cwd=candidate)
        command(["git", "remote", "add", "origin", repository], cwd=candidate)
        command(["git", "fetch", "--depth=1", "origin", revision], cwd=candidate)
        command(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=candidate)
        if command(["git", "rev-parse", "HEAD"], cwd=candidate, capture=True) != revision:
            raise ValueError("Commit baixado difere do commit solicitado.")
    if (root / ".env").exists():
        shutil.copyfile(root / ".env", candidate / ".env")
    elif (candidate / ".env").exists():
        (candidate / ".env").unlink()
    architecture = current.get("architecture") if current else None
    if not architecture:
        architecture = "x64" if os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE", "").lower() == "amd64" else "x86"
    if architecture not in ("x86", "x64"):
        raise ValueError("Arquitetura inválida na instalação.")
    cpu = "x86_64" if architecture == "x64" else "x86"
    python_version = read_record(candidate / "packaging/toolchain.json")["python"]
    if not re.fullmatch(r"3\.13\.\d+", python_version):
        raise ValueError("Versão Python inválida no código baixado.")
    command(["uv", "sync", "--locked", "--no-dev", "--no-default-groups", "--python",
             f"cpython-{python_version}-windows-{cpu}-none"], cwd=candidate, timeout=600)
    record = {"mode": "source", "revision": revision, "architecture": architecture,
              "directory": f"versions/{digest}"}
    python = candidate / ".venv/Scripts/python.exe"
    command([python, "manage.py", "check"], cwd=candidate)
    for name in TOOLS:
        if not (candidate / "packaging/windows" / name).is_file():
            raise ValueError(f"Código sem ferramenta de instalação: {name}.")
    # Read the data identity before migrations, and register it for recovery/removal.
    location = json.loads(maintenance(candidate, record, "describe_installation", capture=True))
    data_root = Path(location["data_root"]).resolve()
    if data_root == root or root in data_root.parents or data_root in root.parents:
        raise ValueError("Programa e dados precisam estar em pastas separadas.")
    info_path = root / "uninstall-info.json"
    info = read_record(info_path) if info_path.exists() else {
        "application": "RestauranteLocal", "schema_version": 1,
        "install_root": str(root), "data_locations": [], "origins": [],
    }
    if info.get("application") != "RestauranteLocal" or Path(info.get("install_root", "")).resolve() != root:
        raise ValueError("Registro de desinstalação inválido.")
    info["data_locations"] = [item for item in info["data_locations"] if item["data_root"] != location["data_root"]] + [location]
    write_record(info_path, info)
    marker.write_text("Preparação dos dados interrompida. Confira o backup e execute Atualizar.bat.", encoding="utf-8")
    maintenance(candidate, record, "initialize_local")
    command([python, "manage.py", "check"], cwd=candidate)
    for name in TOOLS:
        original = candidate / "packaging/windows" / name
        if name.endswith(".ps1"):
            # Windows PowerShell 5.1 requires BOM for Portuguese messages.
            (root / name).write_text(original.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
        else:
            shutil.copyfile(original, root / name)
    write_record(channel, {"repository": repository, "branch": "main"})
    if current:
        write_record(root / "previous.json", current)
    write_record(pointer, record)
    marker.unlink()
    print(f"Código da main instalado: {revision}. Dados preservados em {data_root}.")


def main():
    """Report failures without allowing startup after data preparation fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--check-on-start", action="store_true")
    options = parser.parse_args()
    try:
        update(options.install_root, options.repository, check_on_start=options.check_on_start)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Atualização cancelada: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
