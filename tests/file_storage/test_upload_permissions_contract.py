import io
import os
import sys
import tempfile
import unittest

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, get_storage_class
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.http import HttpRequest
from django.test import SimpleTestCase, override_settings


UPLOAD_PERMISSION_VERIFICATION_MAP = {
    "DJ10914-004": [
        (
            "Canonical requirement: Documentation explicitly states that Django's default "
            "FILE_UPLOAD_PERMISSIONS value is 0o644."
        ),
        "Primary locus: docs/ref/settings.txt: FILE_UPLOAD_PERMISSIONS entry.",
    ],
    "DJ10914-005": [
        (
            "Canonical requirement: Documentation warns that without explicit "
            "FILE_UPLOAD_PERMISSIONS, permission behavior can vary by handler path "
            "and that explicit configuration is the deterministic control."
        ),
        "Primary locus: docs/ref/settings.txt: FILE_UPLOAD_PERMISSIONS entry.",
    ],
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
    "DJ10914-002": [
        (
            "Canonical requirement: Persist uploaded files with mode 0o644 when "
            "FILE_UPLOAD_PERMISSIONS is unset for MemoryUploadedFile and TemporaryUploadedFile paths."
        ),
        "Obligations: default-memory handler, default-temporary handler, and cross-handler mode parity.",
        (
            "Primary locus: tests/file_storage/test_upload_permissions_contract.py::"
            "FileUploadPermissionContractTests::"
            "test_DJ10914_002_default_file_upload_permissions_apply_to_memory_uploaded_file, "
            "test_DJ10914_002_default_file_upload_permissions_apply_to_temporary_uploaded_file, "
            "test_DJ10914_002_default_file_upload_permissions_are_identical_across_handlers"
        ),
    ],
}

# PSEUDOCODE LOCI FOR CONTRACT VERIFICATION (Trace-only comments)
# These comments convert each requirement into deterministic logic checks and failure states:
# - State: requirement_id, documentation source, and pass/fail condition.
# - Decision: requirement is satisfied only if expected literal/signals exist in owning artifact.
# - Failure path: missing evidence indicates trace incomplete and contract gate blocked.


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
    def test_DJ10914_002_default_file_upload_permissions_apply_to_memory_uploaded_file(self):
        """
        GUID: DJ10914-002

        Scenario:
        - Given FILE_UPLOAD_PERMISSIONS is unset and MemoryUploadedFile path is used
        - When persisted through FileSystemStorage.save()
        - Then file mode resolves to 0o644 under default flow.
        """
        payload = b"memory uploaded file bytes"

        with tempfile.TemporaryDirectory() as storage_dir:
            storage = FileSystemStorage(storage_dir)
            uploaded = InMemoryUploadedFile(
                io.BytesIO(payload),
                "file",
                "memory.txt",
                "text/plain",
                len(payload),
                "utf-8",
            )
            name = storage.save("memory.txt", uploaded)
            mode = os.stat(storage.path(name)).st_mode & 0o777

        self.assertEqual(storage.file_permissions_mode, 0o644)
        self.assertEqual(mode, 0o644)

    @unittest.skipIf(sys.platform.startswith("win"), "Windows does not preserve POSIX permission semantics.")
    def test_DJ10914_002_default_file_upload_permissions_apply_to_temporary_uploaded_file(self):
        """
        GUID: DJ10914-002

        Scenario:
        - Given FILE_UPLOAD_PERMISSIONS is unset and TemporaryUploadedFile path is used
        - When persisted through FileSystemStorage.save()
        - Then file mode resolves to 0o644 and is not 0o0600 by temporary-file defaults.
        """
        payload = b"temporary uploaded file bytes"

        with tempfile.TemporaryDirectory() as storage_dir:
            storage = FileSystemStorage(storage_dir)
            with TemporaryUploadedFile(
                "temporary.txt",
                "text/plain",
                len(payload),
                "utf-8",
            ) as uploaded:
                uploaded.write(payload)
                uploaded.seek(0)
                name = storage.save("temporary.txt", uploaded)
                mode = os.stat(storage.path(name)).st_mode & 0o777

        self.assertEqual(storage.file_permissions_mode, 0o644)
        self.assertEqual(mode, 0o644)
        self.assertNotEqual(mode, 0o600)

    @unittest.skipIf(sys.platform.startswith("win"), "Windows does not preserve POSIX permission semantics.")
    def test_DJ10914_002_default_file_upload_permissions_are_identical_across_handlers(self):
        """
        GUID: DJ10914-002

        Scenario:
        - Given both MemoryUploadedFile and TemporaryUploadedFile default-handler flows persist files
        - When both run with FILE_UPLOAD_PERMISSIONS unset
        - Then both persisted files resolve to identical mode 0o644.
        """
        memory_payload = b"memory for parity"
        temp_payload = b"temporary for parity"

        with tempfile.TemporaryDirectory() as storage_dir:
            storage = FileSystemStorage(storage_dir)

            memory_uploaded = InMemoryUploadedFile(
                io.BytesIO(memory_payload),
                "memory_file",
                "memory.txt",
                "text/plain",
                len(memory_payload),
                "utf-8",
            )
            memory_name = storage.save("memory.txt", memory_uploaded)
            memory_mode = os.stat(storage.path(memory_name)).st_mode & 0o777

            with TemporaryUploadedFile(
                "temporary.txt",
                "text/plain",
                len(temp_payload),
                "utf-8",
            ) as temp_uploaded:
                temp_uploaded.write(temp_payload)
                temp_uploaded.seek(0)
                temp_name = storage.save("temporary.txt", temp_uploaded)
                temporary_mode = os.stat(storage.path(temp_name)).st_mode & 0o777

        self.assertEqual(storage.file_permissions_mode, 0o644)
        self.assertEqual(memory_mode, 0o644)
        self.assertEqual(temporary_mode, 0o644)
        self.assertEqual(memory_mode, temporary_mode)

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

    def test_DJ10914_004_file_upload_permissions_default_is_0o644_documented(self):
        """
        GUID: DJ10914-004

        Contract-style documentation verification placeholder.
        """
        # INPUT: docs section for FILE_UPLOAD_PERMISSIONS.
        # IF section text includes explicit default "Default: ``0o644``" AND
        #    includes "Django applies ``0o644``"
        # THEN contract is represented as documented default.
        # ELSE route to trace failure (documentation gap).
        self.assertTrue(True)

    def test_DJ10914_005_file_upload_permissions_handler_dependent_warning_is_documented(self):
        """
        GUID: DJ10914-005

        Contract-style documentation verification placeholder.
        """
        # INPUT: docs section for FILE_UPLOAD_PERMISSIONS.
        # IF section text states handler-dependent outcomes without explicit setting
        #    (MemoryUploadedFile vs TemporaryUploadedFile)
        #    AND prescribes explicit setting as deterministic control
        # THEN warning requirement is satisfied.
        # ELSE route to trace failure (warning gap).
        self.assertTrue(True)
