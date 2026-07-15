# MIG-300-003 requirement-to-architecture map

- MIG-300-003: Preserve enum default object identity across locale when importing migration.
- Canonical requirements:
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_003_imported_enum_default_preserves_source_member_identity`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_003_enum_member_identity_survives_locale_change_between_generation_and_import`

## Requirement-to-architecture pressure map

- `MIG-300-003 / AC1` (`is Status.GOOD` on imported migration default):
  - `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Architecture pressure: serialization boundary must not emit locale-derived value text for enum members.
    - Canonical output boundary: member lookup expression, so import-time evaluation returns the same singleton member object.
  - `django/db/migrations/writer.py:MigrationWriter.as_string`
    - Architecture pressure: migration emission boundary must preserve serialized enum expression as-is.
    - Canonical seam behavior: operation-level serialized strings must be locale-neutral at generation time.
  - `tests/migrations/test_writer_enum_default_contracts.py`
    - Verification pressure: explicit AC1 placeholder remains the contract entry point until implementation completes.

- `MIG-300-003 / AC2` (identity stability after locale switch between generation and import):
  - `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Architecture pressure: emitted form must always be member-indexing form even when enum values are lazy/translatable.
  - `django/db/migrations/writer.py:MigrationWriter.as_string`
    - Architecture pressure: generated source text and imports must be deterministic for equivalent operation graphs, independent of locale.
  - `tests/migrations/test_writer_enum_default_contracts.py`
    - Verification pressure: import and execution checks are owned by placeholders in this file until implemented.

## File/module placement decisions

- Ownership of enum-default representation policy: `django/db/migrations/serializer.py` (`EnumSerializer.serialize`)
- Ownership of module emission determinism: `django/db/migrations/writer.py` (`MigrationWriter.as_string`)
- Ownership of contract governance for this issue: `tests/migrations/test_writer_enum_default_contracts.py`

## Contracts / structural interfaces

- `EnumSerializer.serialize`
  - Input: enum-like default value from deconstructed model state.
  - Output: `(string_expression, import_set)` where `string_expression` is `<module>.<Enum>['MEMBER']` and import set includes `import <module>`.
  - Boundaries:
    - Must stay within serializer layer.
    - Must not expose locale-specific value semantics in emitted migration source.

- `MigrationWriter.as_string`
  - Input: migration object graph (`operations`, `dependencies`, imports).
  - Output: fully rendered migration module text and import block.
  - Boundaries:
    - Must consume serializer outputs through existing interface.
    - Must avoid enum-aware branching; locale handling remains encapsulated at serializer boundary.

## Dependency direction

- `MigrationWriter.as_string` depends on serialized fragments and ordered imports produced by `serializer_factory`/serializer classes.
- `EnumSerializer.serialize` depends on `serializer_factory(self.value.value)` only for scalar/value fallback logic in `models.Choices` branch.
- Regression placeholders in `test_writer_enum_default_contracts.py` consume public contracts from writer/serializer only.

## Integration seam skeleton

- Serialization seam:
  - `EnumSerializer.serialize` is the only active writer seam for enum defaults in migration generation.
- Emission seam:
  - `MigrationWriter.as_string` is the only seam that converts operation graph values into executable migration text.
- Verification seams:
  - AC1: `test_mig_300_003_imported_enum_default_preserves_source_member_identity`
  - AC2: `test_mig_300_003_enum_member_identity_survives_locale_change_between_generation_and_import`

## Completion/risk posture

- Each traced obligation is mapped to explicit module boundary and interface contract.
- Structural artifact changed: [traceability mapping file] now includes Yesod/SPARC-A commitments.
- No behavior changes were made in this phase; this is architecture placement only.
