# MIG-300-003 requirement-to-verification map

- MIG-300-003: Preserve enum default object identity across locale when importing migration
- Requirement coverage:
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_003_imported_enum_default_preserves_source_member_identity`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_003_enum_member_identity_survives_locale_change_between_generation_and_import`

- Mapping:
  - `MIG-300-003` -> `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: emitted enum-default literal must retain member-level identity metadata (`module.Enum['MEMBER']`) rather than locale-dependent value text.
    - Scope: serializer emission branch for enum defaults.
  - `MIG-300-003` -> `django/db/migrations/writer.py:MigrationWriter.as_string`
    - Pressure: generated migration source must remain stable and importable across locale switches.
  - `MIG-300-003` -> `tests/migrations/test_writer_enum_default_contracts.py`
    - Pressure: explicit placeholders track ACs until implementation is completed in later SPARC phases.

- Requirement-to-test split:
  - AC1 (`is Status.GOOD` on imported migration default): placeholder obligation #1.
  - AC2 (locale changed between generation and import keeps identity): placeholder obligation #2.

- Canonical verification owner:
  - `tests/migrations/test_writer_enum_default_contracts.py`
