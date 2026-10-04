"""Normalize restaurant logos for immutable previews and thermal printing."""

import base64
from io import BytesIO
import warnings

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 4_000_000
MAX_LOGO_SIZE = (384, 192)


def normalize_logo(upload):
    """Decode PNG/JPEG and produce a bounded monochrome PNG and raster snapshot."""
    try:
        upload.seek(0)
        data = upload.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValidationError("A logo deve ter no máximo 2 MB.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in ("PNG", "JPEG"):
                    raise ValidationError("Selecione uma imagem PNG ou JPG.")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValidationError("A logo deve ter no máximo 4 milhões de pixels.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
        image.thumbnail(MAX_LOGO_SIZE, Image.Resampling.LANCZOS)
        background = Image.new("RGBA", image.size, "white")
        background.alpha_composite(image)
        monochrome = background.convert("L").convert("1")
        png = BytesIO()
        monochrome.save(png, format="PNG")
        # Pillow uses one for white; ESC/POS uses one for a printed black dot.
        padded = Image.new("1", (((monochrome.width + 7) // 8) * 8, monochrome.height), 1)
        padded.paste(monochrome, (0, 0))
        raster = bytes(value ^ 255 for value in padded.tobytes())
        return {"width": monochrome.width, "height": monochrome.height,
                "png_base64": base64.b64encode(png.getvalue()).decode("ascii"),
                "raster_base64": base64.b64encode(raster).decode("ascii")}
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValidationError("Não foi possível ler a logo. Selecione uma imagem PNG ou JPG válida.") from exc
    finally:
        upload.seek(0)
