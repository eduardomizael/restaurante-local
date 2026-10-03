"""Entrypoint for the independent local application."""

import os
import sys


def main():
    """Dispatch Django commands without starting hardware."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
