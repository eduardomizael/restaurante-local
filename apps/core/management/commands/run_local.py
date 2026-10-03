import logging
from logging.handlers import RotatingFileHandler

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from runtime.application import LocalApplication


class Command(BaseCommand):
    help = "Inicia a aplicação local em modo de simulação."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--simulate", action="store_true")
        parser.add_argument("--preview-print", action="store_true")
        parser.add_argument("--no-tray", action="store_true")
        parser.add_argument("--no-browser", action="store_true")

    def handle(self, *args, **options):
        if not options["simulate"] or not options["preview_print"]:
            raise CommandError("Este incremento exige --simulate --preview-print; hardware real ainda não implementado.")
        if not settings.INSTALLATION:
            raise CommandError("Instalação ausente. Execute initialize_local.")
        logs = settings.DATA_DIR / "logs"
        logs.mkdir(exist_ok=True)
        handler = RotatingFileHandler(logs / "runtime.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger = logging.getLogger()
        logger.addHandler(handler)
        previous_level = logger.level
        logger.setLevel(logging.INFO)
        application = LocalApplication(
            settings.DATA_DIR, settings.INSTALLATION["port"], browser=not options["no_browser"],
        )
        try:
            if not application.start():
                self.stdout.write("Instância existente verificada; nenhum componente duplicado.")
                return
            self.stdout.write(f"Simulação disponível em {application.url}")
            if options["no_tray"]:
                while not application.stop_event.wait(0.5):
                    if not application.server_thread.is_alive():
                        raise RuntimeError("Servidor HTTP encerrou inesperadamente.")
            else:
                from runtime.tray import run_tray

                run_tray(application)
        except KeyboardInterrupt:
            pass
        except (OSError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc
        finally:
            try:
                application.stop()
            finally:
                logger.removeHandler(handler)
                handler.close()
                logger.setLevel(previous_level)
