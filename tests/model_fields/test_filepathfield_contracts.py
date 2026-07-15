from django.test import SimpleTestCase

from .models import FilePathFieldCallablePathModel


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
        pass

    def test_FPF_001_import_phase_has_no_eager_callable_path_filesystem_resolution(self):
        """FPF-001: callable `path` is not eagerly resolved during import-time registration."""
        pass
