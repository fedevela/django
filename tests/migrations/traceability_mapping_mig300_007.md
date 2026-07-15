# MIG-300-007 requirement-to-verification map

- MIG-300-007: Non-plain enum-like defaults must remain on legacy non-enum serialization routes and must not introduce enum-member syntax.
- Requirement coverage:
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterNonPlainDefaultSerializationContractsTests.test_mig_300_007_non_plain_enum_like_default_uses_existing_non_enum_serializer_path`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterNonPlainDefaultSerializationContractsTests.test_mig_300_007_repeated_autogeneration_keeps_non_enum_route_for_non_plain_defaults`

## Requirement-to-architecture-seam map

- MIG-300-007 / Obligation A (single default serialization):
  - `django/db/migrations/serializer.py:serializer_factory`
  - Responsibility: keep non-plain enum-like objects from being forced into enum-specific member-index semantics.
  - Responsibility boundary: preserve existing serializer branches and registry precedence.
  - Validation path: dedicated test placeholder in `MigrationWriterNonPlainDefaultSerializationContractsTests`.
- MIG-300-007 / Obligation B (repeated autogeneration stability):
  - `django/db/migrations/writer.py:MigrationWriter.serialize`
  - Responsibility: keep serializer result as authoritative; no enum-specific rewrite in writer boundary.
  - Responsibility boundary: output stability under repeated calls comes from unchanged handoff and unchanged serialized output.
  - Validation path: repeated-autogeneration test placeholder in `MigrationWriterNonPlainDefaultSerializationContractsTests`.

## Mapping completion status

- All mapped obligations point to concrete writer/serializer structures.
- Verification names are discoverable and traceable by requirement ID.
- This map is architecture-only and does not include behavior assertions.
