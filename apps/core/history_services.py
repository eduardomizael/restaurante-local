"""Persist change-history acknowledgment outside the database."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.conf import settings

from apps.core.history_selectors import change_history


def acknowledge_history(fingerprint):
    """Atomically save acknowledgment only for the history actually presented."""
    if fingerprint != change_history()["fingerprint"]:
        raise ValueError("O histórico mudou. Reabra para ver as novidades.")
    directory = Path(settings.DATA_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"fingerprint": fingerprint}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / "change-history-state.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
