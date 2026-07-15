# MIG-300-004 requirement-to-verification map

- MIG-300-004: Deterministic enum-default rendering must be stable across repeated autogeneration and locale transitions.
- Requirement coverage:
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultDeterminismContractsTests.test_mig_300_004_locale_round_trip_repeated_autogeneration_keeps_enum_member_index_text`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultDeterminismContractsTests.test_mig_300_004_deconstruction_reconstruction_stable_enum_class_member_form`

## Requirement-to-implementation-seam map

- `MIG-300-004 / AC1` (repeated makemigrations locale A → B → A keeps emitted member-index form):
  - `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: output must remain `EnumClass['MEMBER']` in serialization contracts.
  - `django/db/migrations/writer.py:MigrationWriter.serialize` (write path)
    - Pressure: generated migration text should preserve stable enum-default fragments across runs.
  - `tests/migrations/test_writer_enum_default_contracts.py`
    - Pressure: explicit placeholder contract preserves deterministic expectation without behavioral assertions in this phase.

- `MIG-300-004 / AC2` (deconstruction/reconstruction under locale-sensitive enum values is stable):
  - `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: avoid value-form alternation and keep member-index representation.
  - `django/db/migrations/writer.py:MigrationWriter.serialize` and migration module execution boundary
    - Pressure: reconstruction path must remain aligned with deconstruction output under equivalent conditions.
  - `tests/migrations/test_writer_enum_default_contracts.py`
    - Pressure: explicit placeholder contract for deterministic roundtrip behavior is recorded and discoverable.

## Mapping completion status

- All MIG-300-004 acceptance behaviors have deterministic traceability coverage through this file.
- No runtime behavior or behavioral assertions introduced in this phase.
