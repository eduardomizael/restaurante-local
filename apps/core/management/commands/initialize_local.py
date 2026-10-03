"""Explicit installation/update with backup, never invoked during startup."""

import json
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command

from runtime.instance_lock import InstanceLock


class Command(BaseCommand):
    help = "Inicializa/atualiza dados locais com backup; exige programa fechado."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=None)

    def handle(self, *args, **options):
        port = options["port"]
        if port is not None and not 1024 <= port <= 65535:
            raise CommandError("Porta deve estar entre 1024 e 65535.")
        data_dir = settings.DATA_DIR
        if data_dir == settings.BASE_DIR or settings.BASE_DIR in data_dir.parents:
            raise CommandError("Use diretório de dados fora dos arquivos do programa.")
        data_dir.mkdir(parents=True, exist_ok=True)
        lock = InstanceLock(data_dir)
        if not lock.acquire():
            raise CommandError("Feche o programa antes de instalar/atualizar.")
        try:
            config_path = data_dir / "installation.json"
            database = data_dir / "db.sqlite3"
            if database.exists() or config_path.exists():
                backup = data_dir / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                backup.mkdir(parents=True)
                if config_path.exists():
                    (backup / "installation.json").write_bytes(config_path.read_bytes())
                if database.exists():
                    with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(backup / "db.sqlite3")) as target:
                        source.backup(target)
                self.stdout.write(f"Backup salvo em {backup}")
            configuration = dict(settings.INSTALLATION)
            configuration.setdefault("secret_key", secrets.token_urlsafe(64))
            configuration["port"] = port or configuration.get("port", 8765)
            temporary = config_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(configuration, indent=2), encoding="utf-8")
            temporary.replace(config_path)
            settings.SECRET_KEY = configuration["secret_key"]
            call_command("migrate", interactive=False, verbosity=options["verbosity"])
            self.stdout.write(self.style.SUCCESS(f"Dados locais preparados em {data_dir}"))
        finally:
            lock.release()
