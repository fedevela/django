# Issue 316 Architecture (FKEY-003)

## Scope anchors
- Canonical requirement: `FKEY-003`
- Scope: keep PK-rename and FK `AlterField` migration behavior structurally sound from planning through execution replay for explicit `to_field` references.
- Non-goals: non-FK dependencies, non-PK rename migration flows.

## Requirement-to-architecture map
- `FKEY-003` planning order pressure → `django/db/migrations/autodetector.py`
  - `MigrationAutodetector.generate_altered_fields`
  - `MigrationAutodetector._sort_migrations`
- `FKEY-003` execution-order pressure → `django/db/migrations/executor.py`
  - `MigrationExecutor._migrate_all_forwards`
- `FKEY-003` stale reference pressure → `django/db/migrations/loader.py`
  - `MigrationLoader.project_state`

## Ownership and boundaries
- `autodetector.py` owns in-memory migration change synthesis boundaries:
  - Inputs: `from_state`, `to_state`, `renamed_fields`, `renamed_models`.
  - Output: ordered operation sequences and auto-dependency edges.
  - Constraint: does not hit the database and remains deterministic.
- `executor.py` owns execution-order semantics:
  - Inputs: requested migration `plan`, `full_plan`, `state`.
  - Output: applied migration state in `full_plan` sequence.
  - Constraint: forward-only ordered replay only; mixed plans remain rejected in `migrate()`.
- `loader.py` owns project-state replay and validation:
  - Input: reconstructed `ProjectState` and rendered models.
  - Output: validated state only if FK explicit targets resolve.
  - Constraint: any stale `to_field` must fail deterministically on replay.

## Architecture pressure handling
- PK rename vs downstream FK alter ordering
  - Placement: detect/reify explicit FK dependency edges in `generate_altered_fields`.
  - Boundary: edge intent is recorded as `op._auto_deps` and consumed only by `_sort_migrations`.
  - Dependency direction: FK dependency metadata flows from rename-metadata context into local operation ordering.
- Ordered execution for forward paths
  - Placement: full-plan-driven replay in `_migrate_all_forwards`.
  - Boundary: plan selection and migration-state render become explicit loop boundaries over `full_plan`.
  - Dependency direction: `MigrationExecutor` receives ordered graph plan and enforces progression by `full_plan` index discipline.
- Stale `to_field` enforcement
  - Placement: validation pass in `MigrationLoader.project_state`.
  - Boundary: post-state construction before executor continuation.
  - Dependency direction: migration graph → state replay → FK target resolution.

## Integration seams and contracts
- `Autodetector` → dependency graph seam:
  - Contract: when an altered FK field has explicit target metadata, it must expose dependency order sufficient for PK rename-before-alter sequencing.
  - Contract owner: `MigrationAutodetector`.
- `Autodetector` → execution seam:
  - Contract: generated operations and `_auto_deps` are stable-inputs consumed by operation sorter and later migration planner.
  - Contract owner: `MigrationAutodetector._sort_migrations`.
- `Executor` replay seam:
  - Contract: forward migrations are applied exactly once and in the sequence defined by the global full graph plan.
  - Contract owner: `MigrationExecutor._migrate_all_forwards`.
- `Loader` validation seam:
 - Contract: explicit FK targets must resolve to existing fields at replay-time; stale names stop execution deterministically.
 - Contract owner: `MigrationLoader.project_state`.

## Structural placeholders / implementation-ready notes
- Keep all behavioral work within existing signatures:
  - `generate_altered_fields`, `_sort_migrations`, `project_state`, `_migrate_all_forwards`.
- No API additions required for this issue; comment anchors should become implementation points.
- Requirement IDs should remain adjacent to each changed code block to preserve traceability.

## Completion status
- One architecture artifact created: `tests/migrations/issue_316_architecture.md`
- All `FKEY-003` obligations mapped to concrete ownership and contracts
- No behavior has been claimed as complete in this phase; current code remains implementation-ready and deterministic
