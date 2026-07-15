# DJANGO12856-002 Architecture Artifact (SEFIRAH/YESOD)

## Requirement-to-Architecture Map

- `DJANGO12856-002` → `tests/migrations/test_commands.py:DJANGO12856_002_VERIFICATIONS` (traceability hub)
- `DJANGO12856-002` → `django/db/models/base.py:Model._check_constraints()`
- `DJANGO12856-002` → `django/core/management/commands/makemigrations.py:Command.handle()`
- `DJANGO12856-002` → `django/core/management/commands/makemigrations.py:Command.write_migration_files()`
- Scenario 1 (`scenario_1_any_invalid_constraint_reference_prevents_emission`) and Scenario 2 (`scenario_2_valid_and_invalid_constraints_short_circuit_migration`) share one pressure:
  - Any invalid `Meta.constraints` `UniqueConstraint` field-reference check must fail the model model-level validation path and prevent migration write for that model.
- Scenario 3 (`scenario_3_all_constraints_valid_no_short_circuit`) introduces the non-error continuation pressure:
  - If all `UniqueConstraint` references resolve, keep existing behavior and allow migration emission path to proceed.

## Ownership and Module Placement

- `django/db/models/base.py` owns canonical validation policy for model-level checks.
- `Model._check_constraints()` owns the pre-flight partitioning pressure:
  - classify each `UniqueConstraint` as valid/invalid via local field checks,
  - emit structural errors for invalid constraints,
  - surface failure signal usable by migration/check orchestration.
- `django/core/management/commands/makemigrations.py` owns migration orchestration and emission boundaries.
- `tests/migrations/test_commands.py` owns deterministic scenario coverage and acceptance mapping for this issue.

## Boundary Definitions

- Validation boundary:
  - Inputs: `cls._meta.constraints` and constraint `fields` entries.
  - Outputs: errors (`checks.Error`) representing invalid local-field references (`models.E012`-family through `_check_local_fields`).
- Migration boundary:
  - Inputs: candidate change set from `MigrationAutodetector`.
  - Outputs: migration write intent and emitted files.
  - Constraint: if a model has invalid `UniqueConstraint` references, write intent for that model must terminate before file emission.
- Check/emit boundary:
  - `handle()` must not silently downgrade constraint validation errors into warnings.
  - Constraint-reference failure remains authoritative for command exit + model emission control.

## Interface/Contract Artifacts

- `Model._check_constraints(databases)`:
  - Input contract:
    - `databases`: iterable of database aliases to evaluate.
    - `cls._meta.constraints`: list of model constraints.
  - Behavior contract:
    - for each `UniqueConstraint`, run `cls._check_local_fields(constraint.fields, "constraints")`;
    - if invalid, aggregate returned errors and mark the model as blocked for migration emission;
    - only valid constraints continue into feature checks (`supports_partial_indexes`, etc.).
- `Command.handle(..., check_changes, ... )`:
  - Input contract:
    - `check_changes` controls failure exit policy.
    - `changes` is a `dict` of app-label -> migration candidates.
  - Behavior contract:
    - receives model-level constraint validation outcome from model validation path;
    - write phase is allowed only for models that cleared the constraint gate.
- `Command.write_migration_files(changes)`:
  - Input contract:
    - only `changes` that passed command-level gate.
  - Behavior contract:
    - must not write migration files for blocked models.

## Dependency-Direction Notes

- Data dependency: `Model._check_constraints()` depends on `Model._check_local_fields()` for deterministic field-reference validation.
- Orchestration dependency: `makemigrations.Command.handle()` depends on model-level validation output to decide whether migration generation is safe to persist.
- One-way direction constraint for this requirement:
  - `base.py` provides validation state → `makemigrations.py` consumes to gate writes.
  - No reverse dependency from command layer back into `_check_constraints`.

## Integration-Seam Skeleton

- **Seam A (constraint preflight):** inside `_check_constraints`, add explicit `valid_constraints` / `invalid` split before feature checks.
- **Seam B (model-level fail signal):** propagate invalid-constraint presence as a model block flag so migration orchestration can skip that model.
- **Seam C (write gating):** in `Command.handle()` / write path, prevent `write_migration_files()` invocation for blocked models.

## Topology and Placement Changes

- No package/module relocations required.
- Minimal delta is architectural scaffolding and traceability:
  - add this architecture artifact,
  - preserve existing locus in test mapping and pseudocode comment anchors.

## Completion status

- Architecture artifact created: `docs/django12856-002-architecture.md`
- All traced obligations now map to owning module(s), contract boundaries, dependency direction, and integration seams.
- The repository has a concrete structure-level artifact for implementation handoff.
