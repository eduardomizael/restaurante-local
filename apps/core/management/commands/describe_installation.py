"""Expose installation paths without starting hardware or disclosing secrets."""

import json

from django.conf import settings
from django.core.management import BaseCommand

from runtime.instance_lock import instance_mutex_name


class Command(BaseCommand):
    help = "Informa a pasta de dados e o mutex para as ferramentas de instalação."
    requires_system_checks = []

    def handle(self, *args, **options):
        self.stdout.write(json.dumps({
            "data_root": str(settings.DATA_DIR.resolve()),
            "mutex_name": instance_mutex_name(settings.DATA_DIR),
        }))
