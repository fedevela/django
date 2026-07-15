# MIG-300-005 requirement-to-architecture map

- MIG-300-005: Restrict member-name rendering to plain enum defaults in mixed-default migrations
- Canonical requirements:
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultMixedDefaultsContractsTests.test_mig_300_005_mixed_defaults_only_plain_enums_use_member_name_serialization`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultMixedDefaultsContractsTests.test_mig_300_005_non_enum_defaults_in_mixed_payloads_keep_original_form`
  - `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultMixedDefaultsContractsTests.test_mig_300_005_non_enum_object_matching_string_shape_avoids_enum_syntax_rewrite`

## Requirement-to-architecture pressure map

- `MIG-300-005 / Obligation A` (plain enum-only member-name rendering in mixed defaults):
  - `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: owns conversion of default enum members into migration-safe member-index literal form.
    - Boundaries: no special casing based on payload shape or peers; contract is enum-instance-only representation.
  - `django/db/migrations/serializer.py:serializer_factory`
    - Pressure: owns dispatch policy; decides whether a default maps to `EnumSerializer` based on runtime type alone.

- `MIG-300-005 / Obligation B` (non-enum defaults keep existing serialization form):
  - `django/db/migrations/serializer.py:serializer_factory`
    - Pressure: non-enum values must remain on their existing serializer branch; no fallback rewrite from value-shaped strings/numbers/callables.
    - Boundaries: preserve current failure/validation semantics by delegating unchanged to registered serializers.
  - `django/db/migrations/serializer.py` (registry-based serializer classes)
    - Pressure: each serializer remains source-of-truth for its value type.

- `MIG-300-005 / Obligation C` (no false enum rewrite for enum-like string-shaped objects):
  - `django/db/migrations/serializer.py:serializer_factory`
    - Pressure: evaluate each value by concrete runtime type, not textual/member-like similarity.
    - Boundary: mixed-default frame has no aggregate heuristic or coalescing rewrite.
  - `django/db/migrations/writer.py:OperationWriter.serialize` and `MigrationWriter.serialize`
    - Pressure: no boundary-level mutation of default representation; delegate raw values through serializer boundaries one-by-one.

## Placement and ownership

- Canonical owner for enum representation policy: `django/db/migrations/serializer.py:EnumSerializer.serialize`.
  - Responsibility: emit `module.EnumClass['MEMBER']` only when runtime value is `enum.Enum` and `serializer_factory` selected.
- Canonical owner for serialization dispatch and mixed-default selection semantics: `django/db/migrations/serializer.py:serializer_factory`.
  - Responsibility: type-driven dispatch and preservation of existing non-enum serializer outputs.
- Canonical owner for operation/default traversal and seam integration: `django/db/migrations/writer.py:OperationWriter.serialize` plus `MigrationWriter.serialize` proxy.
  - Responsibility: consume serialized fragments as a boundary; maintain existing ordering and formatting behavior.
- Canonical ownership for traceability coverage: `tests/migrations/test_writer_enum_default_contracts.py`.
  - Responsibility: contract coverage for MIG obligations A/B/C and requirement mapping continuity.

## Structural contracts

- `EnumSerializer.serialize`
  - Input contract: runtime value resolved to an enum serializer by dispatch.
  - Output contract: expression `<module>.<EnumClass>[<name>]` and import dependency for module.
  - Invariant: only enum-member payloads use member-index syntax.

- `serializer_factory(value)`
  - Input contract: runtime default/object encountered during migration deconstruction.
  - Branch contract:
    - normalize `Promise` / `LazyObject` as before;
    - preserve pre-existing deconstruction / type dispatch order;
    - dispatch by registered serializer type only.
  - Invariant: non-enum defaults remain serialized by their current serializer classes; no shape-based rewrite.

- `OperationWriter.serialize` / `MigrationWriter.serialize`
  - Input contract: operation deconstruction args/kwargs and dependency/default fragments.
  - Output contract: textual migration code fragment and import collection.
  - Invariant: no direct enum-member rewriting at this boundary; do not branch on mixed payload content.

## Dependency direction

- `MigrationWriter` → `OperationWriter` → `MigrationWriter.serialize` (proxy) → `serializer_factory` → serializer classes.
- `serializer_factory` is the direction gate: writer relies on serializer decisions and must remain agnostic to mixed-default heuristics.
- Tests depend on writer/serializer public output contracts only; they must not assume internal rewriting outside these seams.

## Integration seams

- Serialization seam: `serializer_factory` decides serializer class by runtime type.
- Enum-representation seam: `EnumSerializer.serialize` is the only location that emits enum-member syntax.
- Emission seam: `OperationWriter.serialize` / `MigrationWriter.serialize` are the only points that materialize text in migration source.
- Verification seam: `tests/migrations/test_writer_enum_default_contracts.py` maps each obligation to explicit placeholder contracts.

## Completion status (Yesod/SPARC-A gate)

- All three MIG-300-005 obligations map to at least one owning boundary and interface.
- File/module ownership and seam direction are explicit.
- At least one concrete architecture artifact has been created (`tests/migrations/traceability_mapping_mig300_005.md`).
- Artifact remains structurally focused; no implementation/runtime behavior was modified in this phase.
