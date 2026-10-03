"""Explicit bounded equipment checks; no commercial records are created."""

from django.core.management import BaseCommand, CommandError

from hardware.scale.serial_adapter import SerialScale
from hardware.printer.windows_raw import WindowsRawPrinter


class Command(BaseCommand):
    help = "Consulta balança real e/ou imprime teste RAW somente com flags explícitas."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--scale", action="store_true")
        parser.add_argument("--samples", type=int, default=3)
        parser.add_argument("--port", default="COM3")
        parser.add_argument("--print-test", action="store_true")
        parser.add_argument("--printer", default="balanca")

    def handle(self, *args, **options):
        if not options["scale"] and not options["print_test"]:
            raise CommandError("Informe --scale e/ou --print-test. Nenhum equipamento foi aberto.")
        if not 1 <= options["samples"] <= 20:
            raise CommandError("Número de amostras deve estar entre 1 e 20.")
        if options["scale"]:
            adapter = SerialScale(options["port"])
            try:
                for _ in range(options["samples"]):
                    sample = adapter.read()
                    self.stdout.write(f"{sample.device}: líquido={sample.net_weight_grams} g, tara={sample.tare_grams} g, movimento={sample.moving}")
            except (OSError, ValueError) as exc:
                raise CommandError(str(exc)) from exc
            finally:
                adapter.close()
        if options["print_test"]:
            adapter = WindowsRawPrinter(options["printer"])
            try:
                result = adapter.send(
                    "RESTAURANTE LOCAL\nTESTE DE IMPRESSAO - SEM VALOR COMERCIAL\n"
                    "Acentos: refeição, à vontade, açúcar, café\n"
                    "123456789012345678901234567890123456789012345678\n"
                    "[   ] [   ] [   ] [   ] [   ] [   ] [   ] [   ]\n"
                    "Confira largura, acentos, avanço e corte.\nFIM DO TESTE\n"
                )
                self.stdout.write(result.message)
            except Exception as exc:
                raise CommandError(str(exc)) from exc
            finally:
                adapter.close()
