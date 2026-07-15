# DJANGO-11797 Architecture (Yesod / SPARC-A)

## Requirement-to-Architecture Map

- `DJANGO-11797-001`  
  - Structural pressure: preserve initial `values()` grouping intent when entering `annotate()` and later projection narrowing.
- `DJANGO-11797-002`  
  - Structural pressure: enforce slice as a pure row-windowing seam while preserving grouping key shape.
- `DJANGO-11797-003`  
  - Structural pressure: preserve aggregated RHS subquery projection and grouping shape when used as `filter(id=...)`.
  - Structural pressure: avoid RHS scalar rewrite that drops grouped annotation shape in `Exact.process_rhs()`.

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

4. RHS scalar subquery boundary (`django/db/models/lookups.py`)
   - `Exact.process_rhs()` is the only boundary that mutates grouped subquery projection for scalar lookups (`exact` equality).
   - Contracts:
     - For `self.rhs` that is a `Query` and `self.rhs.has_limit_one()`:
       - if `self.rhs.group_by` is not `None`, do not mutate `select`/`annotation_select`/`group_by`; preserve original subquery shape for compile-time SQL projection.
       - if `self.rhs.group_by` is `None`, keep existing scalar-only normalization path (`clear_select_clause()` then `add_fields(['pk'])`).
     - For `self.rhs.has_limit_one()` false, preserve current failure contract (`ValueError`).

## Dependency Direction

- `QuerySet` (`query.py`) -> mutates/pass-through to `Query` (`sql/query.py`) objects.
- `Query` -> provides metadata (`group_by`, `annotation_select`, `low_mark`, `high_mark`) consumed by `SQLCompiler` (`sql/compiler.py`).
- `Query` and `QuerySet` never own SQL rendering details; all SQL emission stays in compiler boundary.
- `BuiltinLookup`/`Field` -> `Exact.process_rhs()` receives RHS `Query` intent and must either preserve grouped shape or invoke legacy scalar rewrite prior to compiling SQL.
- `Exact.process_rhs()` -> `Query` metadata (`has_limit_one`, `group_by`) drives branch selection; does not call compiler internals beyond post-branch delegation.

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

- RHS grouped-subquery seam:
  - API: `QuerySet.filter(lookup_rhs_query)` with exact lookup dispatch
  - State handoff: `Exact.process_rhs()` reads `rhs.has_limit_one()` and `rhs.group_by`
  - Contract enforcement: grouped `rhs` retains its current `select`/`group_by`; ungrouped `rhs` follows legacy pk-only scalar contract
  - SQL materialization: `BuiltinLookup.process_rhs()`/compiler path compiles whichever RHS contract is chosen

## File/Artifact Delta

- Created: `tests/aggregation_regress/ARCHITECTURE_DJANGO-11797.md`
- Existing verification artifacts remain in `tests/aggregation_regress/tests.py` under `DJANGO_11797_REQUIREMENT_MAP`.
- Updated: `tests/aggregation_regress/ARCHITECTURE_DJANGO-11797.md` for lookup-level contract and dependency seams.

## Completion Status

- Traceability: every obligation maps to one or more boundary owners above.
- Readiness: boundaries and contracts are explicit for grouping and slice behavior; structure is implementation-ready.
- Artifact requirement: satisfied (one new architecture artifact added).
