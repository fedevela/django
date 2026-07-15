# MIG-300-007 Architecture Artifact

## Requirement-to-architecture map

- MIG-300-007 / Obligation A: default values that only look like enums must not go through enum member-index rendering.
- MIG-300-007 / Obligation B: repeated autogeneration for non-plain enum-like defaults across locale runs must keep the legacy non-enum serialized representation.

## Ownership and boundaries

- `django/db/migrations/serializer.py:serializer_factory` owns the serialization dispatch boundary and must preserve existing branch precedence while gating enum-specific routing.
- `django/db/migrations/serializer.py:EnumSerializer.serialize` owns the enum-member emission contract and assumes plain enum member input from factory dispatch.
- `django/db/migrations/writer.py:MigrationWriter.serialize` owns the handoff boundary to serialization and must remain a pass-through to `serializer_factory(value).serialize()`.
- `tests/migrations/test_writer_enum_default_contracts.py:MigrationWriterNonPlainDefaultSerializationContractsTests` owns requirement traceability and contract discovery for non-plain defaults.
- `tests/migrations/traceability_mapping_mig300_007.md` owns requirement-to-test-to-seam traceability.

## Architecture pressure and placement

- Serialization policy pressure:
  - Place in `serializer_factory` and preserve dispatch order: lazy/promise normalization, high-priority Django serializer checks, deconstructable fallback, registry-based dispatch.
  - Only plain enum member values are permitted to map to enum-member rendering.
- Boundary-pressure:
  - Place enum-special syntax emission in `EnumSerializer.serialize`.
  - Keep non-plain enum-like and unrelated objects on pre-existing serializer paths (`BaseSerializer` implementations chosen earlier).
- Integration pressure:
  - Keep the migration generation call stack unchanged except for decision ownership at the factory gate.
  - Writer acts as integration seam only and does not add enum post-processing.

## Structural contracts

- `serializer_factory(value)`:
  - Input: runtime object from migration deconstruction.
  - Output: serializer instance implementing `.serialize()`.
- `EnumSerializer.serialize()`:
  - Input contract: plain `enum.Enum` member.
  - Output contract: stable member-index code fragment + enum module import.
  - Invariant: non-plain enum-like objects are not forced into this branch by contract.
- `MigrationWriter.serialize(value)`:
  - Input contract: operation field/default value fragment.
  - Output contract: serialized code and import set.
  - Invariant: serializer return value is forwarded unchanged.

## Dependency direction

- `writer.py` depends on `serializer.py` through `serializer_factory` only.
- `serializer.py` depends on registered serializer contracts and deconstructable contracts.
- Tests depend on public outputs from both writer and serializer boundaries; they do not alter dispatch logic.

## Integration seam skeletons

- Primary seam: `MigrationWriter.serialize -> serializer_factory`
- Secondary seam: `serializer_factory -> serializer registry` and enum registration guard
- Observability seam: `traceability_mapping_mig300_007.md` tracks mapping for requirement pressure and test obligations.

## Completion status

- Requirement obligations mapped to explicit module ownership and integration seams.
- Requirement traceability artifacts added.
- No runtime behavior changes introduced in this phase.
- Repository is structurally ready for implementation work on plain/non-plain enum-like dispatch boundaries.
