# Issue #310/#311 Architecture Artifact (YESOD)

## Requirement-to-architecture mapping

- `ISNULL-002` -> `django/db/models/sql/query.py:Query.build_lookup`
  - Authoritative gate for `__isnull` RHS typing.
  - Enforces non-bool rejection so all lookup emission must pass through this contract.

- `ISNULL-002` -> `django/db/models/sql/query.py:Query.build_filter`
  - Routes both direct (`rhs`/`lookup_name`) and join (`Col`-based) paths into `build_lookup()`.
  - Prevents alternate emission path from bypassing the `__isnull` gate.

- `ISNULL-003` -> `django/db/models/query.py:QuerySet._filter_or_exclude`
  - Shared entrypoint for `filter()` and `exclude()` with the only structural branch as negate.
  - Owns delegation (`add_q`) for `Q` creation and exclusion semantics; should not own raw lookup validation.

- `ISNULL-003` -> `django/db/models/query.py:QuerySet._chain`
  - Preserves existing where-graph state and rebinds to shared cloned query.
  - Ensures chained queryset calls append constraints through the same downstream validation seam.

- `ISNULL-003` -> `django/db/models/query.py:QuerySet.filter` / `QuerySet.exclude` → `QuerySet._filter_or_exclude`
  - API entry seam remains one logical validation channel; parity between public entrypoints is an ownership requirement.

- `ISNULL-003` -> `django/db/models/query_utils.py:Q.__init__`, `Q._combine`
  - `Q` owns logical tree normalization only (`AND`/`OR`/`NOT` combinations and connector metadata).
  - Must not implement lookup RHS policy; it must delegate into query-building ownership.

- `ISNULL-003` -> `django/db/models/sql/query.py:Query.add_q` / `Query._add_q`
  - Owns Q traversal and child dispatch.
  - Must hand each leaf condition into `build_filter` so validation occurs in one place for all composition forms.

## Placement and ownership decisions

- Boundary owner for public construction API: `django/db/models/query.py` (`filter`, `exclude`, `_filter_or_exclude`, `_chain`).
- Boundary owner for composition AST: `django/db/models/query_utils.py` (`Q`, connector/children graph).
- Boundary owner for validation and SQL planning: `django/db/models/sql/query.py` (`add_q`, `_add_q`, `build_filter`, `build_lookup`).
- Boundary owner for execution: `django/db/models/query.py` (`ModelIterable.__iter__` and related compiler execution path).
- Ownership rule: lookup validation policy belongs to SQL planning (`build_lookup`) only; all API and composition seams are allowed to construct/query-shape only.

## Architecture boundaries

- Boundary A (entrypoint parity): `QuerySet.filter` / `QuerySet.exclude` → `_filter_or_exclude`.
  - Inputs: kwargs constraints and negate flag.
  - Output: cloned queryset with a `Q`-encoded condition.
  - Invariant: both methods emit through identical structure and cannot diverge in validation behavior.

- Boundary B (composition boundary): `Q` operators (`&`, `|`, `~`) in `query_utils.py`.
  - Inputs: existing and child Q trees.
  - Output: normalized logical tree.
  - Invariant: no value-type validation for `__isnull` here; only structural composition.

- Boundary C (handoff boundary): `QuerySet` query object → `Query.add_q` → `_add_q`.
  - Inputs: normalized `Q` tree (possibly chained or composed).
  - Output: where-node constraints attached to query state.
  - Invariant: each leaf dispatches to `build_filter`.

- Boundary D (validation boundary): `Query.build_filter` → `Query.build_lookup`.
  - Inputs: lhs + rhs + lookup name.
  - Output: validated lookup node or same validation exception.
  - Invariant: single `_validate_isnull_lookup_rhs` gate for both direct and join lookup construction paths.

- Boundary E (execution boundary): queryset iteration/serialization paths.
  - Inputs: prepared query.
  - Output: SQL execution result.
  - Invariant: must rely on pre-existing compilation-time validation; no duplicated `__isnull` checks.

## Contract/type artifacts (structural contracts, implementation-ready)

- Proposed/anchored helper contract:
  - `Query._validate_isnull_lookup_rhs(lookup_name: str, rhs: object, *, location: str | None = None) -> None`
  - Raise `ValueError` when:
    - `lookup_name == "isnull"`
    - `rhs` is not `bool`
  - Contract fields:
    - `lookup_name` must be normalized at call site.
    - Optional `location` tag identifies source seam (`filter`, `exclude`, `q_leaf`, `chained_query`).
    - Error text/context should remain consistent with existing `ISNULL-002` behavior.

- Contract placement:
  - Invocation remains in `Query.build_lookup` after `lookup_class` resolution and before instantiation.
  - No additional call sites in `query_utils.py` or `query.py` public API methods.

## Dependency direction

- `QuerySet._filter_or_exclude` (query.py) depends on `Q` composition and `Query.add_q`; does not depend on validation policy internals.
- `Query._add_q` (sql/query.py) depends on `Query.build_filter` and delegates to `Query.build_lookup` for all leaves.
- `Query.build_filter` depends on `Query.build_lookup`; no downstream dependency back into API-level methods.
- `Q` modules depend only on immutable composition structures and carry no dependency to SQL validation modules.

## Integration-seam skeleton updates (non-functional placeholder intent)

- `django/db/models/query_utils.py`
  - Keep Q construction and `_combine` methods as structural adapters only.
  - Maintain comment anchors that direct all non-bool `__isnull` checks to SQL query-building layer.

- `django/db/models/query.py`
  - Keep `_filter_or_exclude` as single branch point for `filter`/`exclude` APIs.
  - Keep `_chain` as state-preserving attachment point for later query calls.

- `django/db/models/sql/query.py`
  - Keep `add_q`/`_add_q` tree traversal as one validation entry for all composed predicates.
  - Keep direct and join branches in `build_filter` structurally identical with respect to `build_lookup` handoff.
  - Keep `build_lookup` as the only place to call `_validate_isnull_lookup_rhs`.

## Changed architecture artifact paths

- Updated:
  - `tests/lookup/test_isnull_lookup_validation_architecture.md` (this artifact)
- Traceability map anchors in implementation files already prepared in prior pseudocode phase:
  - `django/db/models/query.py`
  - `django/db/models/query_utils.py`
  - `django/db/models/sql/query.py`
  - `tests/lookup/test_isnull_lookup_validation_contracts.py`

## Completion status

- Structural readiness: yes. All `ISNULL-003` logic obligations have clear owning seams and integration path.
- Traceability: each obligation maps to at least one boundary/ownership location with explicit module anchors.
- Architecture artifact: updated one concrete architecture artifact; no runtime-path behavior changes in this phase.
