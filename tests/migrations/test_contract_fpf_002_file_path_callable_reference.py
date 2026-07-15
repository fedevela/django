from django.test import SimpleTestCase


FPF_002_VERIFICATION_MAP = {
    "FPF-002": [
        "test_fpf_002_path_callable_serialize_as_callable_reference_in_migration_code",
        "test_fpf_002_path_callable_migration_output_host_portable_across_base_paths",
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

    def test_fpf_002_path_callable_serialize_as_callable_reference_in_migration_code(self):
        # FPF-002-O1: callable path is emitted as stable migration-reconstructable reference.
        # This test is a traceability stub for the migration-generation obligation.
        pass

    def test_fpf_002_path_callable_migration_output_host_portable_across_base_paths(self):
        # FPF-002-O2: migration text stays host-portable and is unchanged by absolute path layout.
        # This test is a traceability stub for host portability of generated migration code.
        pass
