# Issue #310 Architecture Artifact (YESOD)

## Requirement-to-architecture mapping

- `ISNULL-002` -> `Query.build_lookup()` in `django/db/models/sql/query.py`
  - Place pre-SQL type gate for `lookup_name == 'isnull'`.
  - Accept only `bool` values for RHS; non-bool must fail fast before SQL lookup construction.
- `ISNULL-002` -> `Query.build_filter()` in `django/db/models/sql/query.py`
  - Ensure both direct (`reffed_expression`) and join (`col`-based) branches route through `build_lookup()` so validation cannot be bypassed by query shape.
- `ISNULL-002` -> `Query.__str__()` and `Query.sql_with_params()` in `django/db/models/sql/query.py`
  - Treat these as compilation entrypoints that require prior validation completion.
- `ISNULL-002` -> `ModelIterable.__iter__()` in `django/db/models/query.py`
  - Preserve the execution seam that never reaches `execute_sql()` if `build_filter()`/`build_lookup()` raised.

## Placement and ownership

- Owning locus: `django/db/models/sql/query.py` / `Query.build_lookup`
  - This method is the authoritative type-validation seam for lookup RHS during query build.
- Supporting seam owner: `django/db/models/sql/query.py` / `Query.build_filter`
  - Owns propagation of resolved lookup operands into where-node branches and therefore must preserve invalid-input abort behavior.
- Execution boundary owner: `django/db/models/query.py` / `ModelIterable.__iter__`
  - Owns transition from compiled query state to `compiler.execute_sql()`.
  - Must rely on upstream validation and never implement `__isnull` policy.

## Architecture boundaries

- Boundary A: **Resolution boundary** (`solve_lookup_type` -> `build_filter` -> `build_lookup`)
  - Inputs: parsed lookup path, `lhs`, and `rhs`.
  - Output: validated `Lookup` object.
  - Error output: `ValueError` for non-bool `__isnull` values and no lookup emission.
- Boundary B: **Compilation boundary** (`Query.__str__` / `sql_with_params`)
  - Inputs: prepared `Query` object after where-node construction.
  - Output: SQL string only if validation completed.
  - Responsibility: do not add validation logic here; depend on upstream guard.
- Boundary C: **Execution boundary** (`ModelIterable.__iter__` -> `compiler.execute_sql`)
- Inputs: a compiled `Query`.
  - Output: result rows.
  - Responsibility: no additional `__isnull` validation in iteration path; preserve failure propagation.

## Contract/type artifacts

- Proposed helper contract (to be implemented in follow-up implementation phase):
  - `Query._validate_isnull_lookup_rhs(lookup_name: str, rhs: object, *, location: str) -> None`
  - Raises `ValueError` when:
    - `lookup_name == 'isnull'`
    - `rhs` is not an instance of `bool`
  - Error context contract: include `'__isnull'` and type diagnostic for the provided `rhs`.
- Invocation requirement:
  - Call only in `build_lookup()` after `lookup_class` resolution and before `lookup_class(lhs, rhs)`.

## Dependency direction

- `Query.build_filter` depends on `Query.build_lookup` for gate enforcement.
- `Query.__str__` and `Query.sql_with_params` depend on the invariant that filters are prevalidated.
- `ModelIterable.__iter__` depends on upstream query-building invariants and does not own lookup-type policy.
- No reverse dependency from lookup SQL renderers (`lookups.py`) into validation policy.

## Integration-seam skeleton (non-executable placeholders)

- `django/db/models/sql/query.py`:
  - Keep `build_lookup()` as the single owning gate location.
  - Keep comments/contract markers visible at both direct and join compilation branches in `build_filter()`.
- `django/db/models/query.py`:
  - Keep `ModelIterable.__iter__` boundary marker indicating that `execute_sql` must only be reachable after filter compilation validation.

## Completion status

- Structural readiness: yes for implementation follow-up.
- Traceability: all obligations from `ISNULL-002` map to explicit seams above.
- Artifact update count: one architecture artifact updated, no behavior-path changes in implementation files.
