# DJANGO12856-003 Architecture Artifact (SEFIRAH/YESOD)

## Requirement-to-Architecture Map

- `DJANGO12856-003` → `tests/invalid_models_tests/test_models.py:DJANGO12856_003_VERIFICATIONS` (traceability hub)
- `DJANGO12856-003` → `django/db/models/base.py:Model._check_unique_constraint_fields()`
- `DJANGO12856-003` → `django/core/management/commands/makemigrations.py:Command._find_invalid_unique_constraint_fields()`
- `DJANGO12856-003` → `django/core/management/commands/makemigrations.py:Command._iter_app_configs_for_constraints()`
- Scenario 1 (`scenario_1_each_constraint_and_model_context`) pressure:
  - emit invalid-field errors grouped by model + each constraint identity.
- Scenario 2 (`scenario_2_per_constraint_multi_field_deterministic_order`) pressure:
  - emit one error per invalid field in declaration order per constraint.
- Scenario 3 (`scenario_3_repeatable_validation_determinism`) pressure:
  - keep deterministic ordering across repeated validation runs.

## File/Module Placement Decisions

- `django/db/models/base.py` owns canonical model-check policy.
  - `Model._check_unique_constraint_fields()` owns deterministic per-model/per-constraint iteration.
- `django/core/management/commands/makemigrations.py` owns orchestration seams.
  - `Command._iter_app_configs_for_constraints()` owns stable app ordering for validation pass.
  - `Command._find_invalid_unique_constraint_fields()` owns deterministic model/error aggregation from validation.
- `tests/invalid_models_tests/test_models.py` remains the non-runtime verification mapping owner for this issue.

## Ownership-Boundary Artifacts

- Validation boundary:
  - Producer: `Model._check_unique_constraint_fields()`
  - Consumer: `Command._find_invalid_unique_constraint_fields()`
  - Exchange: ordered `checks.Error` list with model and constraint context.
- Command boundary:
  - Producer: validation producers (model-level checks)
  - Consumer: migration command control flow in `handle()`
  - Exchange: invalid-constraint error set that can stop migration emission.
- No other layer should mutate or re-order these errors in this requirement.

## Interface / Contract Artifacts

- `Model._check_unique_constraint_fields() -> list[checks.Error]`
  - Inputs:
    - `cls` model under validation.
    - `cls._meta.constraints` in declaration order.
  - Contract:
    - iterate constraints in order.
    - for each `UniqueConstraint`, evaluate `constraint.fields` sequentially.
    - append one invalid-field error for each invalid field.
    - preserve stable grouping keys: `(model_name, constraint_name, field_index)`.
- `Command._iter_app_configs_for_constraints(app_labels) -> list[AppConfig]`
  - Inputs: optional app label set.
  - Contract:
    - sorted app labels produce deterministic candidate order.
    - returns app configs for the validation pass in that order.
- `Command._find_invalid_unique_constraint_fields(app_labels) -> list[checks.Error]`
  - Inputs: `app_labels` passed from command options.
  - Contract:
    - traverse app configs in contract order from `_iter_app_configs_for_constraints`.
    - call each model’s `_check_unique_constraint_fields`.
    - preserve model traversal order and append in-order.

## Dependency-Direction Notes

- Model-level dependency:
  - `_check_unique_constraint_fields` depends on `UniqueConstraint` and `_check_local_fields`.
- Command-layer dependency:
  - `_find_invalid_unique_constraint_fields` depends on `apps.get_app_configs()` / `app_config.get_models()` and consumes model-level errors.
- Direction constraint:
  - model layer produces invalid-field context, command layer consumes it.
  - no reverse dependency from command layer back into model validation internals.

## Integration-Seam Skeletons

- **Seam A (constraint traversal):** inside `_check_unique_constraint_fields`, split concerns into `(constraint, field)` traversal and append errors in declaration order.
- **Seam B (app ordering):** `_iter_app_configs_for_constraints` is the deterministic seam for app-scope iteration.
- **Seam C (model aggregation):** `_find_invalid_unique_constraint_fields` is the command-level seam that turns model-local errors into command-owned error stream.
- **Seam D (emit gate):** if this stream is non-empty, migration write remains blocked by existing command constraints.

## Completion Status

- Concrete architecture artifact created: `docs/django12856-003-architecture.md`
- Requirement obligations are mapped to owning modules, boundaries, contracts, dependency direction, and integration seams.
- Structural readyness for implementation is established; no runtime behavior changed in this phase.
