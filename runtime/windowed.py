"""Start a source installation through pythonw without a console window."""

import ctypes
import io
import os
import sys
import traceback


def main():
    """Run the application and persist/show windowed startup failures."""
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    from django.core.management import execute_from_command_line

    try:
        execute_from_command_line([sys.argv[0], "run_local", *sys.argv[1:]])
        return 0
    except (Exception, SystemExit) as error:
        code = error.code if isinstance(error, SystemExit) else 1
        if code in (None, 0):
            return 0
        from runtime.installation import resolve_data_dir

        logs = resolve_data_dir() / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "startup.log").open("a", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())
        ctypes.windll.user32.MessageBoxW(
            None, f"Não foi possível abrir o programa.\nConfira {logs / 'startup.log'}\n"
            "Execute Atualizar.bat com a aplicação encerrada.", "Restaurante Local", 0x10,
        )
        return code if isinstance(code, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
