# Issue #309 Architecture Artifact (YESOD)

## Requirement-to-architecture mapping

- `ISNULL-001` -> Query-resolution validation pressure in `Query.build_lookup()`:
  - Validate RHS of `__isnull` before lookup instance creation.
  - Accept only strict `bool` RHS values.
- `ISNULL-005` -> Error contract pressure in the same seam:
  - Raise the project’s lookup-validation exception family.
  - Include actionable context in message (`__isnull`, invalid value type).

## Placement and ownership

- Owning locus: `django/db/models/sql/query.py` / `Query.build_lookup`.
  - This method owns lookup-name resolution and RHS binding, so type enforcement for
    `__isnull` must be applied here before lookup instantiation.
- Non-owning locus: `django/db/models/lookups.py` / `IsNull`.
  - No behavior changes in SQL generation should be introduced in this issue.
  - `IsNull.as_sql()` remains an execution-time renderer only.

## Architecture boundaries

- Boundary A: **Resolution boundary**
  - Inputs: `lookup_name`, `rhs`, and `lhs` from query parsing.
  - Output: either a `Lookup` object or early failure.
  - `isnull` RHS type must be decided before `lookup = lookup_class(lhs, rhs)`.
- Boundary B: **Validation family boundary**
 - Existing behavior already uses `ValueError` for lookup-resolution/type checks in this module.
 - Keep exception family as `ValueError` to preserve consistency with existing lookup
   validation failures in query building.

## Contract / type artifact

- Proposed integration contract (pseudocode):
  - `Query._is_bool_lookup_rhs(lookup_name: str, rhs: Any) -> None`
    - No return value.
    - Raises `ValueError` when `lookup_name == 'isnull'` and `rhs` is not `bool`.
    - Error context includes:
      - `'__isnull'`
      - `type(rhs).__name__` (or equivalent type representation)
- Invocation point (required):
  - Immediately after `lookup_class` resolution and before `lookup = lookup_class(lhs, rhs)`.

## Dependency direction

- Dependency direction remains:
  - `Query` (`query.py`) decides and validates RHS.
  - `Query` then instantiates lookup classes from `lookups.py`.
- No reverse dependency: lookup classes do not own `__isnull` RHS type policy.
- No optimizer/compiler/caching path changes.

## Integration-seam skeleton

- `query.py`
  - Add/maintain an explicit gate at `build_lookup()` for `lookup_name == 'isnull'`.
- `lookups.py`
  - Keep existing `IsNull.prepare_rhs = False` and `as_sql()` unchanged.

## Readiness note

- Structural readiness is now established for implementation:
  - Single owning module identified (`query.py`).
  - Contract boundary and dependency direction are explicit.
  - Requirement-to-architecture traceability preserved for `ISNULL-001` and `ISNULL-005`.
