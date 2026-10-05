"""Run the bundled application or explicit maintenance commands."""

import ctypes
import io
import os
import sys
import traceback
from pathlib import Path


def main():
    """Start Django explicitly and surface windowed startup failures."""
    windowed = Path(sys.executable).stem == "RestauranteLocal"
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    arguments = sys.argv[1:] if not windowed else ["run_local", *sys.argv[1:]]
    try:
        execute_from_command_line([sys.argv[0], *arguments])
        return 0
    except (Exception, SystemExit) as exc:
        code = exc.code if isinstance(exc, SystemExit) else 1
        if code in (None, 0):
            return 0
        if not windowed:
            raise
        message = sys.stderr.getvalue() if isinstance(sys.stderr, io.StringIO) else str(exc)
        from runtime.installation import resolve_data_dir

        logs = resolve_data_dir() / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "startup.log").open("a", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())
        ctypes.windll.user32.MessageBoxW(
            None, f"Não foi possível abrir o programa.\n\n{message}\n\n"
            "Execute Atualizar.bat com o aplicativo fechado.\n"
            f"Detalhes: {logs / 'startup.log'}", "Restaurante Local", 0x10,
        )
        return code if isinstance(code, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
