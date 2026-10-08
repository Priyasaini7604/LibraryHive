"""Upload pipeline security (SECURITY.md section 9)."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from PIL import Image

from apps.core.exceptions import PayloadTooLarge, ValidationFailed
from apps.core.images import process_upload


def _image_bytes(fmt="JPEG", size=(800, 600), mode="RGB", exif=None) -> bytes:
    buffer = io.BytesIO()
    image = Image.new(mode, size, color=(200, 120, 40) if mode == "RGB" else (200, 120, 40, 128))
    kwargs = {"exif": exif} if exif is not None else {}
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def _upload(data: bytes, name="photo.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)


class ImagePipelineTests(SimpleTestCase):
    def test_valid_jpeg_becomes_webp_with_thumbnail(self):
        result = process_upload(_upload(_image_bytes(size=(3000, 2000))))
        display = Image.open(io.BytesIO(result.display))
        thumb = Image.open(io.BytesIO(result.thumbnail))
        self.assertEqual(display.format, "WEBP")
        self.assertEqual(max(display.size), 1920)
        self.assertEqual(max(thumb.size), 480)
        self.assertEqual((result.width, result.height), display.size)

    def test_png_with_alpha_is_accepted(self):
        result = process_upload(_upload(_image_bytes("PNG", mode="RGBA"), "a.png", "image/png"))
        self.assertEqual(Image.open(io.BytesIO(result.display)).format, "WEBP")

    def test_exif_and_gps_metadata_are_stripped(self):
        exif = Image.Exif()
        exif[0x010F] = "SpyCam"  # Make
        exif[0x8825] = {2: (28.0, 36.0, 0.0)}  # GPS IFD (latitude)
        result = process_upload(_upload(_image_bytes(exif=exif.tobytes())))
        output = Image.open(io.BytesIO(result.display))
        self.assertFalse(output.getexif())
        self.assertNotIn(b"SpyCam", result.display)

    @override_settings(MAX_UPLOAD_BYTES=1000)
    def test_oversize_file_is_rejected(self):
        with self.assertRaises(PayloadTooLarge) as ctx:
            process_upload(_upload(_image_bytes(size=(400, 400))))
        self.assertEqual(ctx.exception.status, 413)
        self.assertEqual(ctx.exception.code, "FILE_TOO_LARGE")

    def test_non_image_renamed_jpg_is_rejected(self):
        with self.assertRaises(ValidationFailed) as ctx:
            process_upload(_upload(b"#!/bin/sh\necho owned\n" * 20))
        self.assertEqual(ctx.exception.code, "FILE_TYPE")

    def test_svg_is_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        with self.assertRaises(ValidationFailed) as ctx:
            process_upload(_upload(svg, "x.jpg", "image/jpeg"))
        self.assertEqual(ctx.exception.code, "FILE_TYPE")

    def test_gif_is_rejected(self):
        with self.assertRaises(ValidationFailed) as ctx:
            process_upload(_upload(_image_bytes("GIF", mode="RGB"), "x.gif", "image/gif"))
        self.assertEqual(ctx.exception.code, "FILE_TYPE")

    @override_settings(MAX_IMAGE_PIXELS=10_000)
    def test_decompression_bomb_is_rejected(self):
        with self.assertRaises(ValidationFailed) as ctx:
            process_upload(_upload(_image_bytes(size=(200, 200))))
        self.assertEqual(ctx.exception.code, "FILE_TYPE")
