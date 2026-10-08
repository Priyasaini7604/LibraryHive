"""Image upload pipeline (BACKEND_ARCHITECTURE.md section 12, SECURITY.md section 9).

Every uploaded image is verified from its content (never its name or
Content-Type), size- and pixel-limited, then re-encoded to WEBP. Re-encoding
strips EXIF/GPS metadata and any embedded payload. The original is discarded.
"""

import io
import warnings
from dataclasses import dataclass

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

from .exceptions import PayloadTooLarge, ValidationFailed

ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
DISPLAY_MAX_EDGE = 1920
THUMBNAIL_MAX_EDGE = 480
WEBP_QUALITY = 82


@dataclass(frozen=True)
class ProcessedImage:
    display: bytes
    thumbnail: bytes
    width: int
    height: int
    original_size: int


def _reject_type() -> ValidationFailed:
    return ValidationFailed("Upload a JPG, PNG or WEBP image.", code="FILE_TYPE")


def process_upload(uploaded_file) -> ProcessedImage:
    max_bytes = settings.MAX_UPLOAD_BYTES
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_bytes:
        raise PayloadTooLarge(f"Images must be {max_bytes // (1024 * 1024)} MB or smaller.")

    raw = uploaded_file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise PayloadTooLarge(f"Images must be {max_bytes // (1024 * 1024)} MB or smaller.")

    Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                if probe.format not in ALLOWED_FORMATS:
                    raise _reject_type()
                probe.verify()
            image = Image.open(io.BytesIO(raw))
            if image.width * image.height > settings.MAX_IMAGE_PIXELS:
                raise ValidationFailed("This image has too many pixels.", code="FILE_TYPE")
            image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationFailed("This image has too many pixels.", code="FILE_TYPE") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise _reject_type() from None

    image = ImageOps.exif_transpose(image)
    image.info = {}  # drop EXIF, XMP, ICC and any other embedded metadata
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    display = image.copy()
    display.thumbnail((DISPLAY_MAX_EDGE, DISPLAY_MAX_EDGE))
    thumb = image.copy()
    thumb.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE))

    return ProcessedImage(
        display=_encode_webp(display),
        thumbnail=_encode_webp(thumb),
        width=display.width,
        height=display.height,
        original_size=len(raw),
    )


def _encode_webp(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    # A fresh image object carries no EXIF; we never pass exif= to save().
    image.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=4)
    return buffer.getvalue()
