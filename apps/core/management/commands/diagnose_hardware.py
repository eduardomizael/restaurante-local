"""Explicit bounded equipment checks; no commercial records are created."""

from time import monotonic, sleep

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
        parser.add_argument("--protocol", choices=("USECB2", "PROT_F"), default="USECB2")
        parser.add_argument("--interval", type=int, default=500, help="Intervalo em ms (0 a 2000).")
        parser.add_argument("--show-frames", action="store_true", help="Exibe quadros recebidos em hexadecimal.")
        parser.add_argument("--probe", choices=("passive", "query"), help="Sonda bruta: escuta ou consulta 0x04.")
        parser.add_argument("--duration", type=int, default=10)
        parser.add_argument("--print-test", action="store_true")
        parser.add_argument("--printer", default="balanca")

    def handle(self, *args, **options):
        if options["probe"]:
            if not options["scale"] or options["print_test"] or not 1 <= options["duration"] <= 60:
                raise CommandError("Sonda exige --scale, duração de 1 a 60 s e não admite impressão.")
            adapter = SerialScale(options["port"], protocol=options["protocol"])
            def emit(elapsed, block):
                self.stdout.write(f"t={elapsed:.3f}s bytes={len(block)} hex={block.hex()} texto={block!r}")
            try:
                total = adapter.probe(duration=options["duration"], query=options["probe"] == "query", emit=emit)
            except (OSError, ValueError) as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"Resumo da sonda {options['probe']}: {total} bytes recebidos; porta fechada.")
            return
        if not options["scale"] and not options["print_test"]:
            raise CommandError("Informe --scale e/ou --print-test. Nenhum equipamento foi aberto.")
        if not 1 <= options["samples"] <= 120:
            raise CommandError("Número de amostras deve estar entre 1 e 120.")
        if not 0 <= options["interval"] <= 2000:
            raise CommandError("Intervalo deve estar entre 0 e 2000 ms.")
        if options["scale"]:
            adapter = SerialScale(options["port"], protocol=options["protocol"])
            failures = 0
            try:
                for index in range(options["samples"]):
                    started = monotonic()
                    try:
                        sample = adapter.read()
                        tare = "não informada" if sample.tare_grams is None else f"{sample.tare_grams} g"
                        weight = "indisponível" if sample.protocol == "PROT_F" and sample.moving else f"{sample.net_weight_grams} g"
                        result = (f"{sample.device}: líquido={weight}, "
                                  f"tara={tare}, movimento={sample.moving}")
                    except (OSError, ValueError) as exc:
                        failures += 1
                        result = f"FALHA {type(exc).__name__}: {exc}"
                    frame = adapter.last_frame
                    size = "não recebido" if frame is None else str(len(frame))
                    self.stdout.write(f"{index + 1}/{options['samples']}: {result}; "
                                      f"bytes={size}; duração={monotonic() - started:.3f} s")
                    if options["show_frames"] and frame is not None:
                        self.stdout.write(f"quadro_hex={frame.hex()}")
                    if index + 1 < options["samples"]:
                        sleep(options["interval"] / 1000)
            finally:
                adapter.close()
            self.stdout.write(f"Resumo: {options['samples'] - failures} válidas; {failures} falhas.")
            if failures:
                raise CommandError("Diagnóstico concluído com falhas; examine tamanhos, tempos e quadros acima.")
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
