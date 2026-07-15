# MIG-300-002 requirement-to-verification map

- MIG-300-002: Locale-safe enum-default migration emission during import
- Requirement coverage:
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_002_generated_enum_member_default_migration_import_uses_member_reference_under_translated_value_locale`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_002_generated_enum_member_default_migration_execution_succeeds_across_locale_variants`

- Mapping:
  - `MIG-300-002` -> `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: emitted default for plain enum members must remain member-name-based and non-locale-sensitive.
    - Scope: serialization contract consumed by migration module import.
  - `MIG-300-002` -> `django/db/migrations/writer.py` (generated migration rendering/importability boundary)
    - Pressure: generated migration text remains valid under locale changes when imported and executed.
  - `MIG-300-002` -> `tests/migrations/test_writer_enum_default_contracts.py`
    - Pressure: placeholders preserve explicit obligations and deterministic traceability to canonical requirement ID.

- Requirement-to-test split:
  - AC1 (locale translation changes enum value string): placeholder obligation #1.
  - AC2 (two locale variants for import + execute): placeholder obligation #2.
