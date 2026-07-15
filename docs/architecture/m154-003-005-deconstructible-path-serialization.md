# Issue #156 Architecture (Yesod / SPARC A): stable deconstructible path serialization

## Scope

- GUID: `M154-003` — keep existing top-level deconstructible path strings unchanged.
- GUID: `M154-005` — deterministic nested-path shape across repeated references and reordered fields.
- This phase does **not** change migration semantics outside path-shape formatting.

## Requirement-to-architecture mapping

- `M154-003` → `django/db/migrations/serializer.py`
  - `DeconstructableSerializer._serialize_path` owns top-level path normalization contract.
  - `tests/migrations/test_writer_nested_reference_traceability.py`
    - `test_m154_003_top_level_deconstructible_path_remains_non_nested_format_after_nested_fixes` is the traceability sink.
- `M154-005` → `django/db/migrations/serializer.py`
  - `DeconstructableSerializer.serialize_deconstructed` owns deterministic call-shape contract.
  - `DeconstructableSerializer._serialize_path` owns canonical dotted-path resolution.
  - `tests/migrations/test_writer_nested_reference_traceability.py`
    - `test_m154_005_nested_reference_shape_is_deterministic_across_reordered_and_repeated_fields`.

## Placement and ownership decisions

- **Serialization boundary owner**: `django/db/migrations/serializer.py` remains the only implementation home for deconstructible path formatting.
- **Topology rule**: no new modules are introduced; all deterministic logic stays in `DeconstructableSerializer`.
- **Test boundary owner**: `tests/migrations/test_writer_nested_reference_traceability.py` owns requirement-level behavioral invariants and keeps coverage intent decoupled from serializer internals.

## Architectural contracts (to be implemented)

- `serialize_deconstructed(path, args, kwargs) -> (expr: str, imports: set[str])`
  - Contract: output a deterministic function-call representation from deconstructed components.
  - Ownership: `DeconstructableSerializer`.
  - Constraint: kwargs serialized in stable key order; args preserve declaration order from `deconstruct()`.
- `_serialize_path(path: str) -> (name: str, imports: set[str])`
  - Contract: produce a single dotted path and minimal import set for a deconstructible path token.
  - Determinism pressure (`M154-005`): all successful resolution attempts traverse the same ordered scan strategy and must produce identical shape across repeated calls.
  - Stability pressure (`M154-003`): top-level targets remain emitted in non-nested `module.symbol` form when valid direct module resolution exists.

## Dependency direction

- `Field`/custom deconstructible objects → `MigrationWriter.serialize(...)` → `serializer_factory(...)` → `DeconstructableSerializer.serialize_deconstructed(...)` → `_serialize_path(...)`.
- `serializer_factory` remains only caller-facing entry; internal helpers (`serialize_deconstructed`, `_serialize_path`) stay sink-facing to centralize path-resolution policy.
- `tests/migrations/...` imports and executes `MigrationWriter` only; tests should not link to internal helper details beyond contract assertions.

## Integration seams and placeholders

- **Seam S1** (`value.deconstruct()`): entry seam for serialized targets. Contract continues through existing tuple format `(path, args, kwargs)`; no shape changes.
- **Seam S2** (`_serialize_path` cache-free scan): internal deterministic rewrite candidate loop; must be deterministic across invocations.
- **Seam S3** (string+imports boundary): final output contract between serializer and migration operation text builders.

## Structural readiness check

- Deterministic behavior has explicit architectural home in one owning module.
- Responsibility boundaries are stable (serializer owns path strategy; tests own verification intent).
- Dependency direction remains one-way and acyclic relative to the feature area.
- Requirement IDs are traceable from logic pressure (`serializer.py`) to verification sinks (`test file`) with no semantic coupling outside this area.

## Completion status

- Status: **architecture-ready** for implementation pass.
