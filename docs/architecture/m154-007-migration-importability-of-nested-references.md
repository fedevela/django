# Issue #158 Architecture (Yesod / SPARC A): migration importability of nested deconstruction references

## Scope

- GUID: `M154-007` — corrected nested references emitted in migration files must be importable when migrations are imported.
- Scenario 1: `<module>.Outer.Inner` resolves during migration import.
- Scenario 2: `<module>.Thing.State` resolves during migration import.
- Non-goal: runtime serialization semantics outside migration import-time resolution of deconstruction paths.

## Requirement-to-architecture map

- `M154-007.S1` → `tests/migrations/test_writer_nested_reference_traceability.py::NestedReferenceTraceabilityTests::test_m154_007_import_time_nested_outer_inner_reference_resolves_from_generated_migration_module`
- `M154-007.S2` → `tests/migrations/test_writer_nested_reference_traceability.py::NestedReferenceTraceabilityTests::test_m154_007_import_time_nested_enum_reference_resolves_from_generated_migration_module`
- `M154-007` → `django/db/migrations/serializer.py`
- `M154-007` → `django/db/migrations/writer.py`
- `M154-007` → `django/db/migrations/loader.py`
- `M154-007` → `django/core/management/commands/makemigrations.py`

## Ownership and boundary decisions

- **Serializer boundary owner**: `django/db/migrations/serializer.py` owns deconstruct token emission through `DeconstructableSerializer.serialize_deconstructed` and `DeconstructableSerializer._serialize_path`.
- **Migration rendering boundary owner**: `django/db/migrations/writer.py` owns string shape output and import-set construction for operation arguments.
- **Command boundary owner**: `django/core/management/commands/makemigrations.py` owns filesystem emission timing and path selection (`writer.path`, write pass).
- **Load boundary owner**: `django/db/migrations/loader.py` owns migration module import execution and failure surfacing at import time.
- **Verification boundary owner**: `tests/migrations/test_writer_nested_reference_traceability.py` owns required import-time success criteria via the two S1/S2 placeholders.

## Architectural contracts

- `DeconstructableSerializer._serialize_path(path: str) -> (name: str, imports: set[str])`
  - Contract: emit a dotted symbol name that can be re-imported from the generated module path.
  - Constraint: candidate module resolution must only succeed when all attr steps exist on imported objects in chain.
  - Constraint: serialized path for migration files must align with `import <module>` usage from this serializer.
- `MigrationWriter.as_string() -> str`
  - Contract: preserve serialized dotted references and import statements in emitted migration module text.
  - Constraint: no post-filtering that strips required class-module imports for nested attribute paths.
- `MigrationLoader.load_disk()` import flow
  - Contract: generated migration files are imported as modules and must fail fast with surfaced import/attribute errors.
  - Constraint: generated module import becomes the effective acceptance boundary for `M154-007` scenarios.
- `makemigrations` write flow
  - Contract: generated migration text is persisted to `writer.path` before subsequent import attempts by loader.
  - Constraint: path selection must be deterministic per app and `MIGRATION_MODULES` configuration.

## Dependency direction and integration seams

- Dependency direction is `value deconstruct -> MigrationWriter.serialize -> DeconstructableSerializer -> _serialize_path -> generated imports + expression string`.
- Dependency direction continues `MigrationWriter.as_string -> file system write in makemigrations -> MigrationLoader.load_disk -> import_module(migration_path)`.
- Integration seam S1 (`serialize_deconstructed` to `_serialize_path`): path emission and import-set creation must remain cohesive.
- Integration seam S2 (`MigrationWriter.as_string` to filesystem write): generated text becomes the contract boundary for loader importability checks.
- Integration seam S3 (`MigrationLoader.load_disk` to import_module` migration module): any unresolved nested attr in emitted path becomes import-time runtime failure and must be eliminated.

## Readiness checklist

- All mapped obligations have concrete owning modules and seams.
- Test requirement IDs are preserved end-to-end in the traceability map.
- Ownership boundaries do not expand beyond migration serialization, rendering, write orchestration, and import loading.
- Dependency flow is one-way from serialized expression to import-time execution.

## Completion status

- Status: **architecture-ready** for implementation of `M154-007` importability pressure.
