"""Check runtime ownership without opening hardware or changing data."""

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from runtime.instance_lock import InstanceLock


class Command(BaseCommand):
    help = "Confere se o aplicativo está fechado para uma atualização."
    requires_system_checks = []

    def handle(self, *args, **options):
        if not settings.DATA_DIR.is_dir():
            return
        lock = InstanceLock(settings.DATA_DIR)
        if not lock.acquire():
            raise CommandError("Feche o programa pela bandeja antes de atualizar.", returncode=2)
        lock.release()
