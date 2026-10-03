"""Tray integration imported only by the explicit runtime."""

from runtime.state import state


def run_tray(application):
    """Run the tray on the calling main thread.

    Args:
        application: Started LocalApplication to control.
    """
    import pystray
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (64, 64), "#173d36")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 14, 54, 50), radius=7, fill="#e8f4ee")
    draw.rectangle((20, 22, 44, 32), fill="#173d36")

    def open_home(icon, item):
        application.browser_open(application.url)

    def open_status(icon, item):
        application.browser_open(application.url + "status/")

    def open_configuration(icon, item):
        application.browser_open(application.url + "configuration/equipment/")

    def pause(icon, item):
        state.toggle_pause()

    def exit_runtime(icon, item):
        application.request_stop()
        icon.stop()

    icon = pystray.Icon("restaurante-local", image, "Restaurante Local", pystray.Menu(
        pystray.MenuItem("Abrir atendimento", open_home, default=True),
        pystray.MenuItem("Status", open_status),
        pystray.MenuItem(
            lambda item: "Retomar leitura" if state.snapshot()["paused"] else "Pausar leitura", pause,
        ),
        pystray.MenuItem("Sair", exit_runtime),
        pystray.MenuItem("Equipamentos", open_configuration),
    ))
    try:
        icon.run()
    finally:
        icon.stop()
