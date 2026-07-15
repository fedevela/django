# DJANGO-11797 Architecture (Yesod / SPARC-A)

## Requirement-to-Architecture Map

- `DJANGO-11797-001`  
  - Structural pressure: preserve initial `values()` grouping intent when entering `annotate()` and later projection narrowing.
- `DJANGO-11797-002`  
  - Structural pressure: enforce slice as a pure row-windowing seam while preserving grouping key shape.

## Ownership and Boundary Placement

1. Queryset API boundary (`django/db/models/query.py`)
   - `QuerySet.annotate()` keeps query-shape orchestration at API level and should preserve grouping intent into query metadata rather than rewriting `group_by` via projection.
   - `QuerySet.__getitem__()` remains the row-limiting boundary for userland slicing.
   - Contract: this layer changes API-visible intent only (annotation/slice request), not SQL clause semantics directly.

2. Query shape boundary (`django/db/models/sql/query.py`)
   - `Query.set_values()` is the projection boundary and owns `values_select`, select masks, and grouping metadata stabilization.
   - `Query.set_limits()` is the row-windowing boundary and owns only `low_mark`/`high_mark`.
   - Contracts:
     - `set_values()` must retain upstream grouping metadata when it narrows/selects fields after grouped annotations.
     - `set_limits()` must be orthogonal to `group_by`, `annotation_select`, and join/filter structure.

3. SQL compilation boundary (`django/db/models/sql/compiler.py`)
   - `SQLCompiler.get_group_by()` owns translation from query metadata to SQL grouping terms.
   - `SQLCompiler.as_sql()` owns final query clause order and limit/offset emission.
   - Contracts:
     - `get_group_by()` should treat explicit `query.group_by` as authoritative grouping seed for grouped semantics in this issue.
     - `as_sql()` must append limit/offset as a terminal clause only.

## Dependency Direction

- `QuerySet` (`query.py`) -> mutates/pass-through to `Query` (`sql/query.py`) objects.
- `Query` -> provides metadata (`group_by`, `annotation_select`, `low_mark`, `high_mark`) consumed by `SQLCompiler` (`sql/compiler.py`).
- `Query` and `QuerySet` never own SQL rendering details; all SQL emission stays in compiler boundary.

## Integration-Seam Skeletons

- Grouping preservation seam:
  - API: `values()` + `annotate(contains_aggregate=True)` path
  - State handoff: `QuerySet.annotate()` -> `Query.set_group_by`/`group_by` metadata on `Query`
  - Projection preservation: `Query.set_values()`
  - SQL materialization: `SQLCompiler.get_group_by()`
- Slice preservation seam:
  - API: `QuerySet.__getitem__(slice)` path
  - State handoff: `QuerySet.__getitem__()` -> `Query.set_limits()`
  - SQL materialization: `SQLCompiler.as_sql()` limit/offset tail emission

## File/Artifact Delta

- Created: `tests/aggregation_regress/ARCHITECTURE_DJANGO-11797.md`
- Existing verification artifacts remain in `tests/aggregation_regress/tests.py` under `DJANGO_11797_REQUIREMENT_MAP`.

## Completion Status

- Traceability: every obligation maps to one or more boundary owners above.
- Readiness: boundaries and contracts are explicit for grouping and slice behavior; structure is implementation-ready.
- Artifact requirement: satisfied (one new architecture artifact added).
