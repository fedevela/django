# ORDERBY-004 Architecture Decision Record

## Canonical requirement
- `ORDERBY-004` [RED]: Keep duplicate-elision scoped to `get_order_by()` and apply the same normalized full-fragment matching across all supported ordering expression types so non-`RawSQL` terms keep correct emitted order and direction semantics.

## Requirement-to-architecture map
- `ORDERBY-004-S1` owns dedupe capture and fan-in for all supported ordering-term branches in `get_order_by()` (branch outputs collapse into a single `(expr, is_ref)` stream before duplicate handling).
- `ORDERBY-004-S1` locates structural control in `django/db/models/sql/compiler.py:get_order_by()` branch phase before dedupe.
- `ORDERBY-004-S2` owns dedupe collision on exact normalized body + direction + params for semantically identical terms.
- `ORDERBY-004-S2` maps to the `seen` set key check in `django/db/models/sql/compiler.py:get_order_by()`.
- `ORDERBY-004-S3` owns collision safety by requiring body+direction+params equality for all expression types.
- `ORDERBY-004-S3` maps to the dedupe key construction in `django/db/models/sql/compiler.py:get_order_by()` without any expression-type discriminator.

## Placement and ownership
- Primary owner is `SQLCompiler` in `django/db/models/sql/compiler.py`.
- `SQLCompiler` owns ordering-term normalization and duplicate-elision policy.
- `SQLCompiler` owns the `result` output contract and dedupe `seen` keys.
- `OrderBy`/`RawSQL`/`F()`/`Function` and annotation-driven expression nodes own compiled `(sql, params)` and direction behavior only.
- `SQL expression nodes` do not own dedupe policy and must remain format/semantics producers.
- `tests/ordering/test_orderby_rawsql_trace.py` owns scenario contracts for `ORDERBY-004`.
- `tests/ordering/test_orderby_rawsql_trace.py` owns the trace map `ORDERBY_004_REQUIREMENT_TO_TESTS`.

## Contract/type interfaces
- Input seam contract for dedupe:
  - Internal term stream: `(expr, is_ref)` accumulated from all ordering branches in one list.
  - Resolution: `resolved = expr.resolve_expression(...)` before SQL compilation.
- Key seam contract:
  - `sql, params = self.compile(resolved)`.
  - `direction_key`: `"DESC"` when suffix indicates descending, otherwise `"ASC"`.
  - `without_ordering = _normalize_order_by_fragment_for_dedupe(sql_without_direction)`.
  - `params_hash = make_hashable(params)`.
  - `dedupe_key = (without_ordering, direction_key, params_hash)`.
- Output seam contract:
  - If `dedupe_key` already in `seen`, skip term.
  - Else append `(resolved, (sql, params, is_ref))` to `result` and add key to `seen`.

## Dependency direction notes
- Dedup decision direction stays inward to `SQLCompiler.get_order_by()`.
- `get_order_by()` depends on:
  - query-order metadata (`order_by`, `extra_order_by`, `annotation_select`, `extra_select`, `standard_ordering`, `meta ordering`, `combinator`)
  - expression resolution and SQL compilation (`resolve_expression`, `compile`)
  - existing formatting-normalization helper (`_normalize_order_by_fragment_for_dedupe`)
  - existing `make_hashable` utility for params

## Integration seam / scaffolding
- Concrete seam:
  - Unified dedupe loop inside `get_order_by()` right after `sql, params = self.compile(resolved)`.
  - This seam replaces branch-local dedupe logic; all supported term sources already flow through it via `order_by` list capture.
- Integration guardrail:
  - No type-specific dedupe branch in this function is allowed; one key tuple drives all duplicate decisions.
- Type-collision guardrail:
  - `without_ordering` is full-fragment canonicalized SQL, not type metadata; cross-type collision is prevented only by true semantic equality in rendered SQL and params.

## Completion status
- Requirement-to-architecture traceability is present with `S1`–`S3` mapped to a concrete seam in `get_order_by()`.
- Architecture artifact added: `docs/internals/orderby-004-architecture.md`.
- No runtime behavior changes were introduced in this phase.
