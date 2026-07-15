# DJANGO12856-001 Architecture Artifact (SEFIRAH/YESOD)

## Requirement-to-Architecture Map

- `DJANGO12856-001` → `tests/invalid_models_tests/test_models.py:DJANGO12856_001_VERIFICATIONS` (traceability hub)
- `DJANGO12856-001` → `django/db/models/base.py`:
  - `_check_local_fields()`: field-reference classification and error-ID policy
  - `_check_constraints()` (constraint loop): integration seam where reference validation must run before feature checks
- `DJANGO12856-001` Scenario 1 (`bad_name`) / Scenario 2 (`inherited_field`) / Scenario 3 (`m2m_field`) share one pressure class: deterministic local-field resolution and local-only acceptance for `UniqueConstraint.fields`

## Module Placement and Ownership

- `django/db/models/base.py` owns model validation orchestration for `Model.check()`.
- `Model._check_local_fields()` owns raw field-name resolution semantics (`fields`, `attname`, local-vs-inherited, m2m detection).
- `Model._check_constraints()` owns per-constraint validation orchestration and decides whether feature checks for a given constraint should run.
- `tests/invalid_models_tests/test_models.py` owns deterministic verifications and scenario IDs for the issue.

## Boundary Definitions

- Validation boundary:
  - Inputs: model metadata (`cls._meta`) and constraint definitions (`cls._meta.constraints`).
  - Outputs: check messages (`checks.Error`, `checks.Warning`) tied to the model class.
- Error-ID boundary:
  - `models.E012-family` is the contract target for invalid name resolution in constraint context.
  - Existing `_check_local_fields()` already emits `E012`, `E013`, `E016`; constraint-specific adaptation is an architectural boundary at call-site level in `_check_constraints()`.
- Database-feature checks boundary:
  - `supports_table_check_constraints`, `supports_partial_indexes`, `supports_deferrable_unique_constraints` checks must not execute for a `UniqueConstraint` whose field references already failed structural validation.

## Contracts (Interface-Level)

- `Model._check_local_fields(fields, option)`
  - Input contract:
    - `fields`: iterable of field name strings intended for uniqueness-like validation.
    - `option`: diagnostic label for emitted messages.
  - Output contract:
    - Returns a list of `checks.Error` objects.
    - Non-empty on any unresolved or invalid referenced name under the requested option.
- `Model._check_constraints(databases)`
  - Input contract:
    - `databases`: iterable db aliases.
  - Output contract:
    - Returns aggregated warnings/errors.
    - For each `UniqueConstraint`, local-field validation must execute before constraint capability checks.
    - If local validation returns non-empty, constraint validation should transition to a local-only error state and skip subsequent per-constraint feature checks.

## Dependency-Direction Notes

- Data dependency: `_check_constraints()` depends on `_check_local_fields()` for stable, deterministic field-reference validation.
- Feature boundary: `_check_constraints()` remains the single caller that decides whether to execute `W027/W036/W038` style feature checks.
- Direction: `_check_local_fields()` is generic utility; `_check_constraints()` is the higher-level policy owner for sequencing.

## Integration-Seam Skeleton

- **Seam A (per-constraint preflight):** inside `_check_constraints`, identify `UniqueConstraint` entries first and run `_check_local_fields(constraint.fields, "constraints")`.
- **Seam B (skip gate):** if preflight emits errors for that constraint, move to an error-only branch and do not execute constraint-specific feature checks for that same constraint instance.
- **Seam C (continuation):** for valid references, continue to existing feature checks.

## Topology and Placement Changes

- No topological moves required.
- Only structural documentation/artifacts are updated in this phase.
- Existing pseudocode blocks in `base.py` already represent the intended flow and are now aligned to the architecture map.

## Completion status

- Structural artifact created: `docs/django12856-001-architecture.md`
- All three traced obligations are mapped to owning modules, boundaries, contracts, and seams.
- Repository now has a concrete architecture artifact to guide implementation.
