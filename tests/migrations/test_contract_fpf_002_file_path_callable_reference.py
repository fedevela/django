import importlib.util
import os
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from django.db import models
from django.db.migrations.writer import MigrationWriter


FPF_002_VERIFICATION_MAP = {
    "FPF-002": [
        "test_fpf_002_path_callable_serialize_as_callable_reference_in_migration_code",
        "test_fpf_002_path_callable_migration_output_host_portable_across_base_paths",
    ],
}

FPF_004_VERIFICATION_MAP = {
    "FPF-004": [
        "test_fpf_004_string_path_deconstruction_generates_string_literal_path_argument",
        "test_fpf_004_migration_output_shape_stable_for_existing_string_path_models",
    ],
}

FPF_005_VERIFICATION_MAP = {
    "FPF-005": [
        "test_fpf_005_makemigrations_fails_when_path_callable_is_not_importable",
        "test_fpf_005_no_opaque_path_value_written_for_invalid_callable",
    ],
}


class FilePathFieldCallablePathSerializationContractTests(SimpleTestCase):
    """
    Contract artifacts for FPF-002:
    FilePathField.path callable deconstruction and migration portability.

    See canonical requirement:
    - Scenario 1: migration contains callable path reference, not host path.
    - Scenario 2: output remains stable across host filesystem layouts.
    """

    def _serialize_file_path_field(self, path):
        field = models.FilePathField(path=path)
        serialized, imports = MigrationWriter.serialize(field)
        return serialized, imports

    def _load_remote_callable(self, base_dir):
        module_name = "fpf002_contract_file_path_callable_module"
        module_path = Path(base_dir) / f"{module_name}.py"
        module_path.write_text(
            "\n".join(
                [
                    "def get_local_upload_path():",
                    "    return 'from-temp-host'",
                ]
            )
        )
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, spec, module_name

    def _cleanup_module(self, module_name, old_module):
        if module_name in sys.modules:
            del sys.modules[module_name]
        if old_module is not None:
            sys.modules[module_name] = old_module

    def test_fpf_002_path_callable_serialize_as_callable_reference_in_migration_code(self):
        def get_local_upload_path():
            return "dynamic-host-path"

        name, path, args, kwargs = models.FilePathField(
            path=get_local_upload_path
        ).deconstruct()
        self.assertEqual(path, "django.db.models.FilePathField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs["path"], get_local_upload_path)
        serialized, imports = self._serialize_file_path_field(get_local_upload_path)
        self.assertIn(
            "tests.migrations.test_contract_fpf_002_file_path_callable_reference."
            "get_local_upload_path",
            serialized,
        )
        self.assertIn("import tests.migrations.test_contract_fpf_002_file_path_callable_reference", imports)
        self.assertEqual(name, "file_path")
        self.assertNotIn(os.path.sep, serialized)

    def test_fpf_002_path_callable_migration_output_host_portable_across_base_paths(self):
        with tempfile.TemporaryDirectory() as first_base, tempfile.TemporaryDirectory() as second_base:
            # Simulate generation on different host directory layouts by loading the
            # same callable symbol from two temporary module locations.
            name = "fpf002_contract_file_path_callable_module"
            old_module = sys.modules.get(name)
            first_module, _, module_name = self._load_remote_callable(first_base)
            first_output, first_imports = self._serialize_file_path_field(first_module.get_local_upload_path)
            self._cleanup_module(module_name, old_module)

            second_module, _, _ = self._load_remote_callable(second_base)
            second_output, second_imports = self._serialize_file_path_field(second_module.get_local_upload_path)
            self._cleanup_module(module_name, old_module)

            self.assertEqual(first_output, second_output)
            self.assertEqual(first_imports, second_imports)
            self.assertIn("fpf002_contract_file_path_callable_module.get_local_upload_path", first_output)
            self.assertNotIn(first_base, first_output)
            self.assertNotIn(second_base, second_output)


class FilePathFieldStringPathMigrationContractTests(SimpleTestCase):
    """FPF-004 migration-locus traceability placeholders."""

    def test_fpf_004_string_path_deconstruction_generates_string_literal_path_argument(self):
        """FPF-004 Scenario 1: FilePathField path passed as string remains a string token."""
        path = "/var/data/example_dir"
        name, field_path, args, kwargs = models.FilePathField(path=path).deconstruct()
        self.assertEqual(name, "file_path")
        self.assertEqual(field_path, "django.db.models.FilePathField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs["path"], path)
        self.assertIsInstance(kwargs["path"], str)

        serialized, imports = self._serialize_file_path_field(path)
        self.assertIn("FilePathField(path='/var/data/example_dir')", serialized)
        self.assertEqual(imports, set())
        self.assertIn("example_dir", serialized)
        self.assertNotIn("pathlib", imports)

    def test_fpf_004_migration_output_shape_stable_for_existing_string_path_models(self):
        """FPF-004 Scenario 1: existing migration content for string path is accepted unchanged."""
        path = "/var/data/example_dir"
        existing_migration_code = "models.FilePathField(path=%r)" % path
        field = models.FilePathField(path=path)

        serialized, imports = self._serialize_file_path_field(field.path)
        self.assertEqual(serialized, existing_migration_code)
        self.assertEqual(imports, set())

        # Ensure host/path separators are preserved as provided, not rewritten/expanded.
        self.assertIn(path, serialized)


class FilePathFieldPathCallableImportabilityContractTests(SimpleTestCase):
    """FPF-005 migration-locus runtime checks."""

    def test_fpf_005_makemigrations_fails_when_path_callable_is_not_importable(self):
        """
        FPF-005 Scenario 1: non-importable callable path must fail deterministically
        during migration serialization.
        """
        with self.assertRaisesMessage(ValueError, "deconstructable"):
            self._serialize_file_path_field(lambda: "dynamic-host-path")

        def make_nested_callable():
            def nested_path():
                return "nested-host-path"

            return nested_path

        nested_path = make_nested_callable()
        with self.assertRaisesMessage(ValueError, "local/nested callable"):
            self._serialize_file_path_field(nested_path)

    def test_fpf_005_no_opaque_path_value_written_for_invalid_callable(self):
        """
        FPF-005 Scenario 2: no fallback opaque migration value is emitted for invalid
        path callables.
        """
        def make_nested_callable():
            def nested_path():
                return "nested-host-path"

            return nested_path

        path_callable = make_nested_callable()
        with self.assertRaisesMessage(ValueError, "local/nested callable"):
            models.FilePathField(path=path_callable).deconstruct()
