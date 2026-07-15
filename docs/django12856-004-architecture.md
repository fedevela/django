# DJANGO12856-004 Architecture Artifact (SEFIRAH/YESOD)

## Requirement-to-Architecture Map

- `DJANGO12856-004` → `tests/invalid_models_tests/test_models.py:DJANGO12856_004_VERIFICATIONS`
- `DJANGO12856-004` `scenario_1_unique_and_together_invalid_fields_align_in_check_run` →  
  - `django/db/models/base.py:Model.check()`  
  - `django/db/models/base.py:Model._check_unique_together()`  
  - `django/db/models/base.py:Model._check_unique_constraint_fields()`  
  - `django/db/models/base.py:Model._check_constraints(databases)`  
  - `django/core/management/commands/makemigrations.py:Command._find_invalid_unique_constraint_fields()`  
  - `django/core/management/commands/makemigrations.py:Command.handle()`
- `DJANGO12856-004` `scenario_2_with_unique_together_baseline_remains_unchanged` →  
  - `django/db/models/base.py:Model._check_unique_together()`
- `DJANGO12856-004` `scenario_3_valid_unique_together_behavior_unchanged` →  
  - `django/db/models/base.py:Model._check_unique_together()`  
  - `django/core/management/commands/makemigrations.py:Command.handle()`
- `DJANGO12856-004` `state_transition` →  
  - `django/core/management/commands/makemigrations.py:Command.handle()`  
  - `django/core/management/commands/makemigrations.py:Command._find_invalid_unique_constraint_fields()`  
  - `django/db/models/base.py:Model.check()`

## File/Module Placement and Ownership

- `django/db/models/base.py` owns all model validation semantics.
  - `Model.check()` owns validation orchestration and non-short-circuit error aggregation.
  - `_check_unique_together()` owns legacy `unique_together` field checks and message-family contract.
  - `_check_unique_constraint_fields()` owns deterministic field-reference extraction for `UniqueConstraint` entries.
  - `_check_constraints()` owns post-reference constraint capability checks.
- `django/core/management/commands/makemigrations.py` owns migration command control flow.
  - `_find_invalid_unique_constraint_fields()` owns command-owned validation collection pass.
  - `handle()` owns preflight gating before autodetector initialization and migration write.
- `tests/invalid_models_tests/test_models.py` owns scenario traceability and acceptance evidence for this issue.

## Boundary Definitions

- Validation boundary:
  - `Model._check_unique_together()` and `Model._check_unique_constraint_fields()` are both field-reference producers.
  - `Model._check_constraints()` consumes only metadata already validated by reference checks before feature checks.
  - `Command.handle()` consumes the command-level aggregated error stream and decides whether to continue.
- Error-family boundary:
  - `models.E012`-family is the alignment target for missing/non-local field references from both mechanisms.
  - No `E013`/`E016` semantic changes are introduced for `unique_together`; legacy behavior remains boundary-local in `_check_unique_together()`.
- Migration boundary:
  - `handle()` must keep `unique_together` execution unchanged and only add preflight alignment for `UniqueConstraint` field references.
  - Failure boundary is command stop before autodetector + write phases when preflight errors are present.

## Contracts (Interface-Level)

- `Model.check(**kwargs) -> list[checks.Error]`
  - Inputs:
    - model-level metadata and `kwargs.get("databases")`.
  - Contract:
    - execute index/ordering/unique/constraint checks as additive list concatenation.
    - emit all local-field errors from `unique_together` and `UniqueConstraint` paths in one pass.
- `Model._check_unique_constraint_fields() -> list[checks.Error]`
  - Input:
    - `cls._meta.constraints`.
  - Contract:
    - iterate `UniqueConstraint` entries.
    - for each, call `_check_local_fields(constraint.fields, option)`.
    - return all field-resolution errors without filtering.
- `Command._find_invalid_unique_constraint_fields(app_labels) -> list[checks.Error]`
  - Inputs:
    - optional app labels.
  - Contract:
    - deterministic app/model ordering.
    - aggregate model-level `UniqueConstraint` field-reference failures.
    - pass raw errors unchanged to caller.
- `Command.handle(..., check_changes, ...)`
  - Inputs:
    - app labels and migration command options.
  - Contract:
    - run preflight with `_find_invalid_unique_constraint_fields`.
  - Branch:
    - if errors: raise `CommandError` and exit before autodetector/write setup.
    - otherwise: preserve existing migration path.

## Dependency-Direction Notes

- Data dependency: `_check_constraints()` and `_check_unique_together()` both depend on `_check_local_fields()` for local-field resolution.
- Structural dependency: `_check_unique_constraint_fields()` depends on command-level traversal in `_find_invalid_unique_constraint_fields()` only for orchestration, preserving model-layer ownership.
- Direction constraint:
  - Model layer emits structured errors.
  - Command layer decides run continuation and writes.
  - No command-side dependency injects or rewrites model validation logic.

## Integration-Seam Skeletons

- **Seam A (single-pass additive validation):** inside `Model.check()`, keep all relevant check lists additive so `unique_together` and `constraints` outcomes co-exist in one run.
- **Seam B (reference alignment):** in both `_check_unique_together()` and `_check_unique_constraint_fields()`, surface failures through `_check_local_fields` contract (`models.E012` family).
- **Seam C (preflight gate):** in `Command.handle()`, compute constraint-field errors before loader/autodetector flow and fail fast when non-empty.
- **Seam D (legacy preservation):** no edits to `unique_together` behavior beyond error stream co-presence; `with_unique_together` baseline behavior remains structurally unchanged.

## Completion Status

- Architecture artifact created: `docs/django12856-004-architecture.md`
- Every traced scenario maps to module ownership, contracts, boundaries, integration seams, and dependency direction.
- Structural design remains minimal: one documentation artifact plus existing pseudocode anchors in implementation files, no runtime behavior modified in this phase.
