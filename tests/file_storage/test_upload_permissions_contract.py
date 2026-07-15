import io
import os
import sys
import tempfile
import unittest

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, get_storage_class
from django.http import HttpRequest
from django.test import SimpleTestCase, override_settings


UPLOAD_PERMISSION_VERIFICATION_MAP = {
    "DJ10914-001": [
        "Canonical requirement: When FILE_UPLOAD_PERMISSIONS is unset, default resolves to 0o644.",
        "Primary locus: tests/test_utils/tests.py::OverrideSettingsTests::test_override_file_upload_permissions",
    ],
    "DJ10914-003": [
        "Canonical requirement: Explicit FILE_UPLOAD_PERMISSIONS overrides defaults.",
        "Primary locus: tests/file_storage/tests.py::FileStoragePermissions::test_file_upload_permissions",
    ],
    "DJ10914-006": [
        "Canonical requirement: Upload handler selection, request parsing, and storage flow unchanged.",
        (
            "Primary locus: tests/file_uploads/tests.py::FileUploadTests::test_simple_upload, "
            "test_empty_multipart_handled_gracefully, test_fileuploads_closed_at_request_end"
        ),
    ],
}


class FileUploadPermissionContractTests(SimpleTestCase):
    maxDiff = None

    @unittest.skipIf(sys.platform.startswith("win"), "Windows does not preserve POSIX permission semantics.")
    def test_DJ10914_001_default_file_upload_permissions_resolves_to_0o644_when_unset(self):
        """
        GUID: DJ10914-001
        """
        with tempfile.TemporaryDirectory() as storage_dir:
            storage = FileSystemStorage(storage_dir)
            name = storage.save("default-permissions.txt", ContentFile(b"data"))
            mode = os.stat(storage.path(name)).st_mode & 0o777

        self.assertEqual(mode, 0o644)

    @unittest.skipIf(sys.platform.startswith("win"), "Windows does not preserve POSIX permission semantics.")
    @override_settings(FILE_UPLOAD_PERMISSIONS=0o600)
    def test_DJ10914_003_explicit_file_upload_permissions_take_precedence_over_default(self):
        """
        GUID: DJ10914-003
        """
        with tempfile.TemporaryDirectory() as storage_dir:
            storage = FileSystemStorage(storage_dir)
            name = storage.save("explicit-permissions.txt", ContentFile(b"data"))
            mode = os.stat(storage.path(name)).st_mode & 0o777

        self.assertEqual(storage.file_permissions_mode, 0o600)
        self.assertEqual(mode, 0o600)

    def test_DJ10914_006_upload_handler_selection_request_parsing_and_storage_flow_remain_unmodified(self):
        """
        GUID: DJ10914-006
        """
        body = b"--Dj10914\r\n" + (
            b'Content-Disposition: form-data; name="name"\r\n\r\nvalue\r\n'
            b"--Dj10914--\r\n"
        )
        request = HttpRequest()
        request._encoding = "utf-8"
        request.META = {
            "CONTENT_TYPE": "multipart/form-data; boundary=Dj10914",
            "CONTENT_LENGTH": str(len(body)),
        }

        self.assertEqual(
            [handler.__class__.__module__ + "." + handler.__class__.__name__ for handler in request.upload_handlers],
            [
                "django.core.files.uploadhandler.MemoryFileUploadHandler",
                "django.core.files.uploadhandler.TemporaryFileUploadHandler",
            ],
        )

        post, files = request.parse_file_upload(request.META, io.BytesIO(body))
        self.assertEqual(post["name"], "value")
        self.assertEqual(list(files), [])
        self.assertIs(get_storage_class(settings.DEFAULT_FILE_STORAGE), FileSystemStorage)
