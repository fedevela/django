# MIG-300-006 requirement-to-verification map

- MIG-300-006: Preserve migration module structure and current non-enum serialization fragments while migrating enum defaults to member-index rendering.
- Requirement coverage:
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumModuleStructureContractsTests.test_mig_300_006_import_block_and_non_enum_fragment_preserve_shape`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumModuleStructureContractsTests.test_mig_300_006_non_enum_defaults_does_not_change_under_enum_name_rendering`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumModuleStructureContractsTests.test_mig_300_006_non_enum_only_models_keep_output_shape_stable`

## Requirement-to-seam map

- `MIG-300-006 / AC1` (module/import layout remains stable for enum-default migrations):
  - `django/db/migrations/writer.py:MigrationWriter.as_string`
    - Pressure: preserve generated migration module/import scaffold and ordering while allowing enum-import additions required by enum member rendering.
  - `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: emit enum reference text that justifies the minimal enum import delta.
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumModuleStructureContractsTests`
    - Pressure: contract checkpoint for AC1 with placeholder verification only.

- `MIG-300-006 / AC2` (non-enum defaults remain on existing serialization fragments):
  - `django/db/migrations/serializer.py:serializer_factory`
    - Pressure: keep current serializer dispatch for non-enum values so no unrelated shape drift occurs.
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumModuleStructureContractsTests`
    - Pressure: contract checkpoint for non-enum stability obligations.

- `MIG-300-006 / AC3` (non-enum-only model inputs retain output identity):
  - `django/db/migrations/serializer.py`
    - Pressure: maintain existing serializer contracts for non-enum defaults in mixed and non-mixed migrations.
  - `django/db/migrations/writer.py:MigrationWriter.serialize`
    - Pressure: emit migration text without unrelated module-structure drift.
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumModuleStructureContractsTests`
    - Pressure: placeholder contract for output shape continuity.

## Structural contracts

- `MigrationWriter.serialize / as_string`
  - Input contract: operation defaults, including enum and non-enum fragments.
  - Output contract: migration module text plus import set.
  - Invariant: import block should only include non-enum import behavior changes required to support enum-member rendering.

- `serializer_factory` and `EnumSerializer.serialize`
  - Input contract: runtime default values from deconstruction.
  - Output contract: stable fragment for enum defaults and delegated default serializer for non-enum values.
  - Invariant: non-enum serializer branches must remain unchanged unless explicit enum rule applies.

## Completion status (Yesod/SPARC-A gate)

- All three MIG-300-006 obligations map to explicit verification loci.
- A concrete traceability artifact has been added in `traceability_mapping_mig300_006.md`.
- This phase adds no runtime behavior changes; verification placeholders are no-op assertions only.
