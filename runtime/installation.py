"""Installation configuration, separate from commercial configuration."""

import json
from pathlib import Path

from config.environment import env


def resolve_data_dir():
    """Resolve writable data storage without creating files.

    Returns:
        Path: Installation data directory.
    """
    override = env.str("LOCAL_WEIGHING_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(env.str("LOCALAPPDATA"))
    return base / "RestauranteLocal"


def read_installation(data_dir):
    """Read validated installation settings without side effects.

    Args:
        data_dir: Directory containing installation.json.

    Returns:
        dict: Settings, or an empty dict before installation.

    Raises:
        ValueError: Configuration is malformed.
    """
    path = data_dir / "installation.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuração de instalação inválida.")
    port = data.get("port")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Porta HTTP deve estar entre 1024 e 65535.")
    if not isinstance(data.get("secret_key"), str) or len(data["secret_key"]) < 50:
        raise ValueError("Segredo local ausente ou inválido. Execute initialize_local.")
    return data
