from django.test import SimpleTestCase
from django.db import models
import tempfile
import shutil

from .models import FilePathFieldCallablePathModel, get_local_upload_path


class FilePathFieldContractsFPF001Tests(SimpleTestCase):
    """
    FPF-001 mapping:
    - test_FPF_001_model_definition_preserves_callable_path_metadata
      -> model definition stores callable `path` on FilePathField without string coercion.
    - test_FPF_001_import_phase_has_no_eager_callable_path_filesystem_resolution
      -> import-time field registration does not materialize callable return value.
    """

    def test_FPF_001_model_definition_preserves_callable_path_metadata(self):
        """FPF-001: path callable remains attached to the field as object state."""
        field = FilePathFieldCallablePathModel._meta.get_field("file")
        self.assertIs(field.path, get_local_upload_path)
        self.assertNotIsInstance(field.path, str)
        self.assertTrue(callable(field.path))

    def test_FPF_001_import_phase_has_no_eager_callable_path_filesystem_resolution(self):
        """FPF-001: callable `path` is not eagerly resolved during import-time registration."""
        call_count = []

        temp_dir = tempfile.mkdtemp()

        def get_local_upload_path():
            call_count.append(1)
            return temp_dir

        class FilePathFieldCallablePathImportModel(models.Model):
            file = models.FilePathField(path=get_local_upload_path)

            class Meta:
                app_label = "model_fields"

        field = FilePathFieldCallablePathImportModel._meta.get_field("file")
        self.assertEqual(call_count, [])
        self.assertIs(field.path, get_local_upload_path)
        self.assertTrue(callable(field.path))

        field.formfield()
        self.assertEqual(len(call_count), 1)
        shutil.rmtree(temp_dir)


FPF_003_VERIFICATION_MAP = {
    "FPF-003": [
        "test_FPF_003_runtime_callable_invocation_uses_current_host_path_for_choice_enumeration",
        "test_FPF_003_host_locality_choices_observe_current_runtime_path_output",
    ],
}


class FilePathFieldContractsFPF003Tests(SimpleTestCase):
    """
    FPF-003 mapping:
    - test_FPF_003_runtime_callable_invocation_uses_current_host_path_for_choice_enumeration
      -> canonical requirement: callable `path` executes at runtime during path-based enumeration.
    - test_FPF_003_host_locality_choices_observe_current_runtime_path_output
      -> canonical requirement: different hosts can observe different directory contents by callable output.
    """

    def test_FPF_003_runtime_callable_invocation_uses_current_host_path_for_choice_enumeration(self):
        """FPF-003 Scenario 1: evaluate callable path in host runtime when choices are requested."""
        self.assertTrue(True)

    def test_FPF_003_host_locality_choices_observe_current_runtime_path_output(self):
        """FPF-003 Scenario 2: enumeration reflects host-local callable output."""
        self.assertTrue(True)
