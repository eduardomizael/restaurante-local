"""Load project environment configuration without installation side effects."""

from pathlib import Path
import sys

import environ

BASE_DIR = Path(__file__).resolve().parent.parent


def load_environment(path):
    """Read an optional UTF-8 dotenv file with typed defaults.

    Args:
        path: Path to the dotenv file.

    Returns:
        environ.Env: Reader preserving existing process environment values.
    """
    environment = environ.Env(
        DEBUG=(bool, False),
        TIME_ZONE=(str, "America/Sao_Paulo"),
        LOCAL_WEIGHING_DATA_DIR=(str, ""),
        LOCALAPPDATA=(str, str(Path.home() / ".local" / "share")),
    )
    if path.is_file():
        environment.read_env(path, overwrite=False, encoding="utf-8")
    return environment


# Bundled assets live in _internal; optional settings live beside the executable.
PROGRAM_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else BASE_DIR
env = load_environment(PROGRAM_DIR / ".env")
