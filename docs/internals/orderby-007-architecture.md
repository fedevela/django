# ORDERBY-007 Architecture Decision Record

## Canonical requirement
- `ORDERBY-007` [GREEN]: Preserve existing single-line `ORDER BY` dedupe semantics and keep multiline regression coverage for newline variants (`\n`, `\r\n`, `\r`) and true duplicate multiline terms, while preventing false collapses from trailing-line collisions.

## Requirement-to-architecture map
- `ORDERBY-007-S1` (single-line semantics unchanged)
  - Structural pressure: baseline behavior must remain first-occurrence/stable-order duplicate suppression for single-line fragments.
  - Home: `django/db/models/sql/compiler.py:SQLCompiler.get_order_by()` duplicate-elision seam (`seen` / `dedupe_key` check).
  - Mapping: ensure no branch diverts `ORDER BY` clauses away from `get_order_by()` dedupe.
- `ORDERBY-007-S2` (multiline trailing-line collisions)
  - Structural pressure: fragments that collide on tail text only must be compared on full normalized fragment text.
  - Home: `django/db/models/sql/compiler.py:SQLCompiler.get_order_by()` keying step just after `without_ordering = self._normalize_order_by_fragment_for_dedupe(...)`.
  - Mapping: key must be derived from complete normalized fragment, not tail slice.
- `ORDERBY-007-S3` (newline-normalization variants)
  - Structural pressure: keying must canonicalize `\n`, `\r\n`, and `\r` deterministically before dedupe.
  - Home: `django/db/models/sql/compiler.py:SQLCompiler._normalize_order_by_fragment_for_dedupe()`.
  - Mapping: helper is the only place allowed to normalize newline form for dedupe keys.
- `ORDERBY-007-S4` (true multiline duplicates)
  - Structural pressure: fully identical multiline fragments must collapse to one emitted term.
  - Home: `django/db/models/sql/compiler.py:SQLCompiler.get_order_by()` `seen`-set identity semantics.
  - Mapping: exact `dedupe_key` collision is authoritative and suppresses repeats.
- `ORDERBY-007-S5` (regression linking)
  - Structural pressure: ensure cross-feature stability with multiline and single-line order semantics.
  - Home: test boundary (`tests/ordering/test_orderby_007_traceability.py`, plus baseline links to:
    `tests/ordering/tests.py::OrderingTests.test_order_by_f_expression_duplicates`,
    `tests/ordering/tests.py::OrderingTests.test_order_by_multiline_sql` (if/when present),
    `tests/expressions/tests.py::ExpressionTests.test_order_of_operations`).
  - Mapping: no changes to `get_order_by` control-flow semantics beyond full-fragment dedupe keying and newline canonicalization.

## Placement and ownership
- Primary owner: `django/db/models/sql/compiler.py` in `SQLCompiler`.
  - Owns:
    - ordered term capture from `query.order_by` / `query.extra_order_by`;
    - `compile(resolved)` emission path into dedupe domain;
    - `seen` set and duplicate-suppression decision.
- Secondary owner: `SQLCompiler._normalize_order_by_fragment_for_dedupe`.
  - Owns:
    - structural whitespace/newline canonicalization for dedupe-only fragments;
    - quote-aware state transitions.
- Test ownership:
  - `tests/ordering/test_orderby_007_traceability.py` owns requirement traceability for `ORDERBY-007`.
  - Baseline coverage remains in existing tests linked by requirement comments.

## Ownership boundaries
- `get_order_by` boundary:
  - Inputs: ordering terms from all branches (`is_ref` + expression stream), each term with compiled `(sql, params)`.
  - Processing boundary:
    - direction parse/fallback,
    - whitespace-newline canonicalization key path,
    - `dedupe_key` creation.
  - Output boundary: `result.append((resolved, (sql, params, is_ref)))`.
- `_normalize_order_by_fragment_for_dedupe` boundary:
  - Inputs: normalized candidate fragment body string.
  - Outputs: canonical dedupe string used only for keying.
  - Must not alter emitted SQL representation.

## Interface/type and contract artifacts
- Dedupe key contract:
  - `dedupe_key = (normalized_fragment, direction_key, params_hash)`
  - `direction_key` retains parsed `ASC`/`DESC` when available, otherwise malformed-direction fallback marker.
  - Duplicate decision:
    - if key in `seen`, skip emission;
    - else emit and add key.
- Canonicalization contract for `_normalize_order_by_fragment_for_dedupe(sql)`:
  - Input: SQL fragment string.
  - Output: deterministic string for keying only.
  - Invariants:
    - preserve SQL token payload outside whitespace/newline structural normalization,
    - collapse line-ending variants to canonical form,
    - keep helper side-effect free.

## Dependency-direction structure
- `get_order_by` depends inward on query ordering metadata and expression compilation; depends on `_normalize_order_by_fragment_for_dedupe` and `make_hashable`.
- `_normalize_order_by_fragment_for_dedupe` has no new module dependencies and should stay isolated.
- No new outward dependencies are introduced for this issue.

## Integration seams and stubs
- Seam A: rendered fragment ingress
  - `sql, params = self.compile(resolved)` -> `direction_key` parse.
- Seam B: keying seam
  - `without_ordering = _normalize_order_by_fragment_for_dedupe(...)` -> `dedupe_key`.
- Seam C: emission gate
  - `if dedupe_key in seen: continue` -> `result.append(...)`.
- Structural stub for implementation:
  - Add/retain an explicit architecture-level invariant that `dedupe_key` is full-fragment-normalized content, not terminal-line content.

## Completion status
- `ORDERBY-007` mapped to concrete modules, interfaces, boundaries, and integration seams.
- Traceability preserved for all five scenarios (`ORDERBY-007-S1` through `ORDERBY-007-S5`).
- Changed architecture artifact:
  - `docs/internals/orderby-007-architecture.md` created.
- No runtime behavior changes applied in this phase.
