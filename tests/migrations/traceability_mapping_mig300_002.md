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

## MIG-300-002 architecture (Yesod/SPARC-A)

- Requirement-to-architecture pressure map:
  - `MIG-300-002 / AC1` → `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: emit enum defaults as stable member identity (`module.Enum['MEMBER']`), never locale-variant string values.
    - Seam owned by this serializer: transforms enum objects into migration-safe literals.
  - `MIG-300-002 / AC1` → `django/db/migrations/writer.py:MigrationWriter.as_string`
    - Pressure: serialized enum defaults must produce importable migration source under any active locale.
    - Seam owned by this writer boundary: consumes serializer outputs and writes module text.
  - `MIG-300-002 / AC2` → `django/db/migrations/writer.py` + `tests/migrations/test_writer_enum_default_contracts.py`
    - Pressure: one deterministic emitted migration body is reusable across locale variants for import and execution flows.

- Module placement / ownership:
  - Canonical serialization owner: `django/db/migrations/serializer.py` (`EnumSerializer.serialize`).
    - Responsibility: choose locale-stable literal form for enum defaults.
  - Canonical migration emission owner: `django/db/migrations/writer.py` (`MigrationWriter.as_string`).
    - Responsibility: emit source/imports from deconstructed operations without introducing locale coupling.
  - Canonical verification owner: `tests/migrations/test_writer_enum_default_contracts.py`.
    - Responsibility: assert locale-related obligations against contract names and MIG IDs.

- Structural contracts:
  - `EnumSerializer.serialize`:
    - Input: enum-like value being serialized for migration source generation.
    - Output: string form + required imports.
    - Rule for MIG-300-002: member-name indexing form is the only accepted stable representation under locale variation.
  - `MigrationWriter.as_string`:
    - Input: migration object with deconstructed operations and defaults.
    - Output: concrete Python module text + import header section.
    - Rule: operation/default rendering must remain stable over locale switches for the same module text.

- Dependency direction:
  - Writer depends on serializer interface output; writer must not inspect enum internals.
  - Serializer depends on value-level serializer support (`serializer_factory`) for scalar/value emission in model-choice-like branch.
  - Tests depend on both writer/serializer artifacts through public contract surfaces only.

- Integration seams:
  - Serialization seam: `EnumSerializer.serialize` is the single write point for enum default representation.
  - Emission seam: `MigrationWriter.as_string` is the single write point for importable migration text.
  - Verification seam: two MIG-300-002 contract tests map to AC1 and AC2.

- Readiness / completion checks:
  - Each AC is mapped to a stable owning boundary and contract point.
  - No locale/translation implementation details are modified at this architecture stage.
  - Existing test placeholder style is preserved while keeping structure and traceability explicit.
