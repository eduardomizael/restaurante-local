"""Read the bundled change history and installation acknowledgment."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from django.conf import settings


def change_history():
    """Return release groups, newest first, and their content fingerprint."""
    path = Path(settings.BASE_DIR) / "resources" / "change-history.json"
    releases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(releases, list) or not releases:
        raise ValueError("Histórico vazio ou inválido.")
    versions = set()
    for release in releases:
        if not isinstance(release, dict) or any(
            not isinstance(release.get(key), str) or not release[key].strip()
            for key in ("date", "version")
        ):
            raise ValueError("Versão inválida no histórico.")
        date.fromisoformat(release["date"])
        version = release["version"]
        if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
            raise ValueError("Use uma versão no formato maior.menor.correção.")
        if version in versions:
            raise ValueError("Versão repetida no histórico.")
        versions.add(version)
        changes = release.get("changes")
        if not isinstance(changes, list) or not changes:
            raise ValueError("A versão precisa listar suas mudanças.")
        for change in changes:
            if not isinstance(change, dict) or any(
                not isinstance(change.get(key), str) or not change[key].strip()
                for key in ("summary", "description")
            ):
                raise ValueError("Mudança inválida no histórico.")
    fingerprint = hashlib.sha256(json.dumps(releases, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    releases = sorted(releases, key=lambda release: (
        release["date"], tuple(map(int, release["version"].split(".")))
    ), reverse=True)
    for release in releases:
        release["display_date"] = date.fromisoformat(release["date"])
    return {"releases": releases, "fingerprint": fingerprint}


def history_seen(fingerprint):
    """Treat missing or damaged acknowledgment as unseen, without writing."""
    try:
        saved = json.loads((Path(settings.DATA_DIR) / "change-history-state.json").read_text(encoding="utf-8"))
        return isinstance(saved, dict) and saved.get("fingerprint") == fingerprint
    except (OSError, ValueError):
        return False
