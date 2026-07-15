# DJANGO-11797 Architecture (Yesod / SPARC-A)

## Requirement-to-Architecture Map

- `DJANGO-11797-001`  
  - Structural pressure: preserve initial `values()` grouping intent when entering `annotate()` and later projection narrowing.
- `DJANGO-11797-002`  
  - Structural pressure: enforce slice as a pure row-windowing seam while preserving grouping key shape.
- `DJANGO-11797-003`  
  - Structural pressure: preserve aggregated RHS subquery projection and grouping shape when used as `filter(id=...)`.
  - Structural pressure: avoid RHS scalar rewrite that drops grouped annotation shape in `Exact.process_rhs()`.
- `DJANGO-11797-004`  
  - Structural pressure: apply RHS-shape preservation in the shared lookup compiler path so grouped annotated subqueries are handled consistently across models.
  - Structural pressure: preserve explicit `group_by` and `annotation_select` for grouped RHS subqueries in `Exact` and `In` lookups.
- `DJANGO-11797-006`  
  - Structural pressure: constrain behavior changes to grouped RHS paths to keep unrelated shapes stable.
  - Structural pressure: avoid public API, model, migration, schema, and docs contract changes for this fix.

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

4. RHS scalar lookup boundary (`django/db/models/lookups.py`)
   - `Exact.process_rhs()` is the scalar subquery projection boundary for `exact` lookups.
   - Contracts:
     - For RHS `Query` with `has_limit_one()`:
       - if `group_by` is not `None`, preserve `select`/`annotation_select`/`group_by`.
       - if `group_by` is `None`, use legacy scalar normalization (`clear_select_clause()` then `add_fields(['pk'])`).
     - For `has_limit_one()` false, keep current failure contract (`ValueError`).

5. RHS membership lookup boundary (`django/db/models/lookups.py`)
   - `In.process_rhs()` is the membership subquery projection boundary.
   - Contracts:
     - Direct iterable RHS (non-`Query`) remains unchanged:
       - OrderedSet conversion, batching, placeholder generation, and existing empty/alias mismatch behavior.
     - Query RHS path:
       - if `has_select_fields` is `False`, normalize via `clear_select_clause()` and `add_fields(['pk'])`
       - if `has_select_fields` is `True`, preserve existing RHS projection and grouping/annotations unchanged.
     - Contract scope: this branch is isolated to `In`; no unrelated lookup path changes.

## Dependency Direction

- `QuerySet` (`query.py`) -> mutates/pass-through to `Query` (`sql/query.py`) objects.
- `Query` -> provides metadata (`group_by`, `annotation_select`, `low_mark`, `high_mark`) consumed by `SQLCompiler` (`sql/compiler.py`).
- `Query` and `QuerySet` never own SQL rendering details; all SQL emission stays in compiler boundary.
- `BuiltinLookup` receives RHS contract decisions from `Exact.process_rhs()` and `In.process_rhs()`.
- `Exact.process_rhs()` -> reads `Query` metadata (`has_limit_one`, `group_by`) and chooses legacy scalar rewrite vs projection-preserve branches.
- `In.process_rhs()` -> reads `Query` metadata (`has_select_fields`, and `query._db`) and chooses direct-value, legacy-normalization, or preserve branches.
- Shared constraint edge:
  - `Exact` and `In` are the only compiler-side projection-shape mutation sites for grouped RHS in this issue, preventing model-specific branches outside lookup-level shared-path logic.

## Integration-Seam Skeletons

- Grouping preservation seam:
  - API: `values()` + `annotate(...)` path
  - State handoff: `QuerySet.annotate()` -> `Query.set_group_by`/`group_by` metadata on `Query`
  - Projection preservation: `Query.set_values()`
  - SQL materialization: `SQLCompiler.get_group_by()`

- Slice preservation seam:
  - API: `QuerySet.__getitem__(slice)` path
  - State handoff: `QuerySet.__getitem__()` -> `Query.set_limits()`
  - SQL materialization: `SQLCompiler.as_sql()` limit/offset tail emission

- Shared RHS scalar/in seam:
  - API: `QuerySet.filter(lookup=rhs_query)` dispatch via `Exact.process_rhs` and `In.process_rhs`
  - State handoff:
    - `Exact`: `rhs.has_limit_one()` + `rhs.group_by`
    - `In`: `rhs.has_select_fields` + `rhs._db`
  - Guard invariants:
    - grouped/annotated RHS retains current `select`/`group_by` where already defined
    - only ungrouped/non-selected RHS uses PK-only normalization
    - unrelated lookups (non `IN` and non `exact`) stay on pre-existing paths
  - SQL materialization: `BuiltinLookup`/compiler path compiles whichever RHS contract is chosen

- Unrelated-query stability guard seam:
  - No API, model, migration, schema, or docs interfaces are touched.
  - Regression tests for unrelated shapes remain in `tests/aggregation_regress/tests.py` as explicit `DJANGO-11797-006` assertions.

## File/Artifact Delta

- Created: `tests/aggregation_regress/ARCHITECTURE_DJANGO-11797.md`
- Existing verification artifacts remain in `tests/aggregation_regress/tests.py` under `DJANGO_11797_REQUIREMENT_MAP`.
- Updated: `tests/aggregation_regress/ARCHITECTURE_DJANGO-11797.md` for shared-path lookup seam, `In.process_rhs` scope, and `-004/-006` traceability.

## Completion Status

- Traceability: each obligation maps to explicit ownership boundaries and seam points.
- Structural readiness: ownership, boundaries, dependency direction, and integration seams are specified for implementation handoff.
- Artifact requirement: satisfied (one architecture artifact created/updated, focused only on structure and contracts).
