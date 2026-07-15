# MIG-300-006 Architecture Artifact (Yesod/SPARC-A)

## Requirement-to-architecture map

- `MIG-300-006 / AC1`: Preserve migration module/import layout when enum defaults are rendered as member-index while allowing only the minimal import delta needed for enum-class references.
- `MIG-300-006 / AC2`: Preserve existing non-enum serialized fragment shapes when enum rendering policy changes.
- `MIG-300-006 / AC3`: Keep output stable for equivalent non-enum-only inputs.

## Module/file placement

- Canonical serialization ownership remains in `django/db/migrations/serializer.py`:
  - `EnumSerializer.serialize` owns enum-member token shape and import requirements for enum values.
  - `serializer_factory` owns dispatch policy: enum branch vs non-enum branch isolation.
  - `serialize` methods in non-enum classes remain authoritative for unchanged output fragments.
- Canonical assembly ownership remains in `django/db/migrations/writer.py`:
  - `OperationWriter.serialize` owns operation arg traversal and delegation order.
  - `MigrationWriter.as_string` owns migration module text assembly and import normalization.
- Verification ownership stays in `tests/migrations/test_writer_enum_default_contracts.py`:
  - `MigrationWriterEnumModuleStructureContractsTests` anchors AC1-AC3 contracts for future non-enum churn guards.
- Traceability ownership is retained in `tests/migrations/traceability_mapping_mig300_006.md` to keep requirement-to-seam alignment explicit.

## Boundary and contract artifacts

- Serialization boundary: `serializer_factory(value) -> serializer.serialize()`.
  - Contract: return `(serialized_text: str, imports: set[str])`.
  - AC2/AC3 pressure: only enum values may emit member-index syntax; all non-enum values must follow existing serializer branches.
- Dispatch boundary: `EnumSerializer.serialize` may emit `module.EnumClass['MEMBER']`.
  - Contract: include `import module`.
  - AC1 pressure: no synthetic enum-like output for other value types.
- Assembly boundary: `MigrationWriter.serialize` and `OperationWriter.serialize`.
  - Contract: preserve arg traversal order, preserve non-enum forms, keep import collection additive.
  - AC1/AC2 pressure: delegate unchanged behavior for non-enum payloads to avoid unrelated serialization drift.
- Emission boundary: `MigrationWriter.as_string` to rendered migration text/import block.
  - Contract: `from django.db import migrations` + optional `models` normalization and stable import sorting.
  - AC1 pressure: preserve existing module/import scaffold and header layout unless required by enum-member rendering.

## Dependency-direction notes

- `writer.py` -> `serializer.py` is the only active data flow direction for value-to-fragment conversion.
- `serializer.py` does not depend on migration assembly for serialization decisions.
- Tests consume writer/serializer boundaries only; they do not feed behavior back into runtime modules.
- Traceability artifacts depend on implementation and tests and are not imported at runtime.

## Integration seams (with placement notes)

- Primary seam: `MigrationWriter.serialize(value)` -> `serializer_factory(value)`.
  - AC1: isolate enum-specific conversion at this seam.
  - AC2/AC3: keep all other conversion contracts unchanged in their existing serializers.
- Primary seam: operation argument serialization (`OperationWriter._write`) -> `MigrationWriter.serialize`.
  - Keeps mixed default payloads intact while routing each value independently.
- Primary seam: `MigrationWriter.as_string` -> import normalization.
- Secondary seam: generated migration source -> migration loader/runtime import.
  - AC2 requires that emitted enum imports/expressions remain compatible with module import execution, while non-enum shape stays identical.

## Topology check for this phase

- No new modules, directories, or helper utilities are introduced.
- No public signatures changed.
- No runtime logic beyond boundary comments/pseudocode in implementation files.
- Scope limited to placement and traceability to prevent unrelated migration layout churn.

## Changed architecture artifacts

- `tests/migrations/architecture_mig300_006.md` (new)
- `tests/migrations/traceability_mapping_mig300_006.md` (existing traceability map; no behavior change)
- `tests/migrations/test_writer_enum_default_contracts.py` (existing placeholder contract tests)
- `django/db/migrations/serializer.py` (requirement-aligned pseudocode at `EnumSerializer.serialize` and `serializer_factory`)
- `django/db/migrations/writer.py` (requirement-aligned pseudocode at `OperationWriter.serialize` and `MigrationWriter.as_string`)

## Completion status

- All MIG-300-006 obligations now have explicit architectural homes and owners.
- Each changed/created architecture artifact is traceable to AC1/AC2/AC3.
- Concrete architecture artifact updated/created for this phase: complete.
