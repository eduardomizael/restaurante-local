"""Isolated settings for tests; never use operational data."""

from .settings import *  # noqa: F403
import tempfile
import uuid
from pathlib import Path

SECRET_KEY = "test-only-key-not-for-installation"
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": ":memory:",
    "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 5},
    "TEST": {"NAME": Path(tempfile.gettempdir()) / f"local-weighing-test-{uuid.uuid4().hex}.sqlite3"},
}}
