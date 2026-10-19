"""Library photos (#25-#29, PHO-01..06)."""

import io
import threading
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase, override_settings
from PIL import Image

from apps.core.exceptions import AppError
from apps.core.models import AuditLog
from apps.core.storage import public_storage
from apps.libraries import services
from apps.libraries.models import LibraryPhoto

from .base import LibraryTestCase, make_library, make_owner, make_student

PHOTOS = "owner/library/photos/"


def image_bytes(fmt="JPEG", size=(800, 600), exif=None) -> bytes:
    buffer = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    Image.new("RGB", size, color=(200, 120, 40)).save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def upload_file(data=None, name="my photo.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data if data is not None else image_bytes(), content_type=content_type)


class PhotoApiTestCase(LibraryTestCase):
    def setUp(self):
        super().setUp()
        self.library = make_library()
        self.owner = self.as_user(self.library.owner)

    def upload(self, client=None, **kwargs):
        client = client or self.owner
        payload = {"image": upload_file(**kwargs.pop("file", {})), **kwargs}
        return client.post(self.api(PHOTOS), payload, format="multipart")

    def add(self, count=1):
        return [
            services.upload_photo(library=self.library, actor=self.library.owner, uploaded_file=upload_file())
            for _ in range(count)
        ]


class UploadTests(PhotoApiTestCase):
    def test_upload_reencodes_to_webp_and_stores_random_keys(self):
        response = self.upload(caption="Reading hall")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        photo = LibraryPhoto.objects.get()
        self.assertTrue(photo.image.startswith(f"libraries/{self.library.pk}/"))
        self.assertTrue(photo.image.endswith(".webp"))
        self.assertTrue(photo.thumbnail.endswith("_thumb.webp"))
        self.assertNotIn("my photo", photo.image)  # the client file name never reaches the key
        self.assertEqual(data["caption"], "Reading hall")
        self.assertTrue(data["is_cover"])
        storage = public_storage()
        self.assertTrue(storage.exists(photo.image) and storage.exists(photo.thumbnail))
        with storage.open(photo.image) as fh:
            self.assertEqual(Image.open(fh).format, "WEBP")
        self.assertEqual((photo.width, photo.height), (800, 600))
        self.assertTrue(AuditLog.objects.filter(action="photo.upload", library=self.library).exists())

    def test_exif_is_not_stored(self):
        exif = Image.Exif()
        exif[0x010F] = "SpyCam"
        self.assertEqual(self.upload(file={"data": image_bytes(exif=exif.tobytes())}).status_code, 201)
        photo = LibraryPhoto.objects.get()
        with public_storage().open(photo.image) as fh:
            self.assertNotIn(b"SpyCam", fh.read())

    def test_first_photo_is_cover_later_ones_are_not_and_order_increments(self):
        self.upload()
        self.upload()
        self.upload()
        photos = list(LibraryPhoto.objects.order_by("display_order"))
        self.assertEqual([p.is_cover for p in photos], [True, False, False])
        self.assertEqual([p.display_order for p in photos], [0, 1, 2])

    def test_rejects_non_images_and_disguised_files(self):
        for name, data, content_type in [
            ("a.jpg", b"not an image at all", "image/jpeg"),
            ("a.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "image/svg+xml"),
            ("a.jpg", b"<?php system($_GET['c']); ?>", "image/jpeg"),
            ("a.gif", image_bytes("GIF"), "image/gif"),
            ("a.jpg", b"", "image/jpeg"),
        ]:
            response = self.upload(file={"name": name, "data": data, "content_type": content_type})
            self.assertEqual(response.status_code, 400, name)
        self.assertFalse(LibraryPhoto.objects.exists())

    def test_missing_file_is_validation_error(self):
        response = self.owner.post(self.api(PHOTOS), {"caption": "x"}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.json()["details"])

    @override_settings(MAX_UPLOAD_BYTES=2000)
    def test_oversize_upload_is_413(self):
        response = self.upload(file={"data": image_bytes(size=(900, 900))})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error_code"], "FILE_TOO_LARGE")

    @override_settings(MAX_LIBRARY_PHOTOS=2)
    def test_photo_limit(self):
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.upload().status_code, 201)
        response = self.upload()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "PHOTO_LIMIT")
        self.assertEqual(LibraryPhoto.objects.count(), 2)

    def test_students_anonymous_and_owners_without_library_are_blocked(self):
        self.assertEqual(self.client.post(self.api(PHOTOS), {}, format="multipart").status_code, 401)
        self.assertEqual(self.upload(client=self.as_user(make_student())).status_code, 403)
        response = self.upload(client=self.as_user(make_owner()))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "LIBRARY_REQUIRED")

    def test_objects_are_removed_if_saving_fails(self):
        before = (
            set(public_storage().listdir(f"libraries/{self.library.pk}")[1])
            if public_storage().exists(f"libraries/{self.library.pk}")
            else set()
        )
        with mock.patch("apps.libraries.services.audit.record", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                services.upload_photo(library=self.library, actor=self.library.owner, uploaded_file=upload_file())
        self.assertFalse(LibraryPhoto.objects.exists())
        after = (
            set(public_storage().listdir(f"libraries/{self.library.pk}")[1])
            if public_storage().exists(f"libraries/{self.library.pk}")
            else set()
        )
        self.assertEqual(before, after)

    def test_upload_is_throttled(self):
        from django.conf import settings
        from rest_framework.test import APIClient

        rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "upload": "2/hour"}
        client = APIClient()
        client.force_authenticate(self.library.owner)
        with mock.patch("rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES", rates):
            statuses = [
                client.post(self.api(PHOTOS), {"image": upload_file()}, format="multipart").status_code
                for _ in range(3)
            ]
        self.assertEqual(statuses, [201, 201, 429])


class GalleryTests(PhotoApiTestCase):
    def test_list_is_ordered_and_scoped(self):
        self.add(2)
        other = make_library(name="Other Library")
        services.upload_photo(library=other, actor=other.owner, uploaded_file=upload_file())
        data = self.owner.get(self.api(PHOTOS)).json()["data"]
        self.assertEqual(len(data), 2)
        self.assertEqual([p["display_order"] for p in data], [0, 1])
        self.assertEqual(
            set(data[0]), {"id", "url", "thumb_url", "caption", "display_order", "is_cover", "width", "height"}
        )

    def test_update_caption_and_order(self):
        photo = self.add()[0]
        response = self.owner.patch(
            self.api(f"{PHOTOS}{photo.pk}/"), {"caption": " Hall ", "display_order": 5}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        photo.refresh_from_db()
        self.assertEqual((photo.caption, photo.display_order), ("Hall", 5))
        self.assertTrue(AuditLog.objects.filter(action="photo.update").exists())

    def test_set_cover_moves_the_cover(self):
        first, second = self.add(2)
        response = self.owner.post(self.api(f"{PHOTOS}{second.pk}/set-cover/"))
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.is_cover, second.is_cover), (False, True))
        self.assertEqual(LibraryPhoto.objects.filter(is_cover=True).count(), 1)

    def test_database_allows_only_one_cover(self):
        first, second = self.add(2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LibraryPhoto.objects.filter(pk=second.pk).update(is_cover=True)
        first.refresh_from_db()
        self.assertTrue(first.is_cover)

    def test_deleting_the_cover_reassigns_it_to_lowest_display_order(self):
        first, second, third = self.add(3)
        LibraryPhoto.objects.filter(pk=third.pk).update(display_order=0)
        LibraryPhoto.objects.filter(pk=second.pk).update(display_order=1)
        response = self.owner.delete(self.api(f"{PHOTOS}{first.pk}/"))
        self.assertEqual(response.status_code, 200)
        third.refresh_from_db()
        self.assertTrue(third.is_cover)
        self.assertEqual(LibraryPhoto.objects.filter(is_cover=True).count(), 1)

    def test_deleting_the_last_photo_leaves_no_cover(self):
        photo = self.add()[0]
        self.assertEqual(self.owner.delete(self.api(f"{PHOTOS}{photo.pk}/")).status_code, 200)
        self.assertFalse(LibraryPhoto.objects.exists())

    def test_objects_are_deleted_only_after_commit(self):
        photo = self.add()[0]
        keys = [photo.image, photo.thumbnail]
        storage = public_storage()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            services.delete_photo(library=self.library, photo=photo, actor=self.library.owner)
        self.assertTrue(all(storage.exists(k) for k in keys), "objects must survive until the commit")
        for callback in callbacks:
            callback()
        self.assertFalse(any(storage.exists(k) for k in keys))

    def test_rolled_back_delete_keeps_objects(self):
        photo = self.add()[0]
        keys = [photo.image, photo.thumbnail]
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    services.delete_photo(library=self.library, photo=photo, actor=self.library.owner)
                    raise RuntimeError("abort")
        self.assertTrue(all(public_storage().exists(k) for k in keys))
        self.assertTrue(LibraryPhoto.objects.filter(pk=photo.pk).exists())


class PhotoIsolationTests(PhotoApiTestCase):
    def test_another_owners_photo_is_404_everywhere(self):
        other = make_library(name="Other Library")
        theirs = services.upload_photo(library=other, actor=other.owner, uploaded_file=upload_file())
        base = f"{PHOTOS}{theirs.pk}/"
        for response in (
            self.owner.patch(self.api(base), {"caption": "mine"}, format="json"),
            self.owner.post(self.api(base + "set-cover/")),
            self.owner.delete(self.api(base)),
        ):
            self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.caption, "")
        self.assertTrue(public_storage().exists(theirs.image))


class PublicPhotoTests(LibraryTestCase):
    def test_cover_and_gallery_appear_in_discovery_and_detail(self):
        library = make_library(publish=True)
        owner = library.owner
        first = services.upload_photo(library=library, actor=owner, uploaded_file=upload_file(), caption="Hall")
        services.upload_photo(library=library, actor=owner, uploaded_file=upload_file())
        with mock.patch("apps.libraries.selectors.active_seat_count", return_value=1):
            services.refresh_publish_state(library)
        listing = self.client.get(self.api("libraries/")).json()["data"]["items"][0]
        self.assertEqual(listing["cover"], {"thumb_url": public_storage().url(first.thumbnail)})
        detail = self.client.get(self.api(f"libraries/{library.pk}/")).json()["data"]
        self.assertEqual([p["is_cover"] for p in detail["photos"]], [True, False])
        self.assertEqual(set(detail["photos"][0]), {"id", "url", "thumb_url", "caption", "is_cover"})
        self.assertNotIn("display_order", detail["photos"][0])

    def test_library_without_photos_has_no_cover_key(self):
        library = make_library(publish=True)
        listing = self.client.get(self.api("libraries/")).json()["data"]["items"][0]
        self.assertNotIn("cover", listing)
        self.assertEqual(library.photos.count(), 0)


class PhotoLimitConcurrencyTests(TransactionTestCase):
    """Uploads racing for the last slot: exactly one wins (the Library row lock serialises the count).

    The test builds its library without vocabulary rows because a TransactionTestCase flushes the seeded ones.
    """

    @override_settings(MAX_LIBRARY_PHOTOS=2)
    def test_parallel_uploads_cannot_exceed_the_limit(self):
        library = make_library(domain_codes=[], amenity_codes=[])
        services.upload_photo(library=library, actor=library.owner, uploaded_file=upload_file())
        outcomes: list[str] = []
        barrier = threading.Barrier(4)

        def worker():
            try:
                barrier.wait(timeout=10)
                services.upload_photo(library=library, actor=library.owner, uploaded_file=upload_file())
                outcomes.append("ok")
            except AppError as exc:
                outcomes.append(exc.code)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(sorted(outcomes), ["PHOTO_LIMIT", "PHOTO_LIMIT", "PHOTO_LIMIT", "ok"])
        self.assertEqual(LibraryPhoto.objects.filter(library=library).count(), 2)
        self.assertEqual(LibraryPhoto.objects.filter(library=library, is_cover=True).count(), 1)
