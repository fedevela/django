# ORDERBY-003 Architecture Decision Record

## Canonical requirement
- `ORDERBY-003` [RED]: Preserve sort-direction semantics in deduplication so semantically identical `ORDER BY` clauses with different directions (`ASC` vs `DESC`) remain distinct entries, while exact duplicates with the same normalized body and direction are reduced to one.

## Requirement-to-architecture map
- `ORDERBY-003-S1`  
  Obligation: distinctness by sort direction when SQL body matches.  
  Ownership: `get_order_by()` duplicate-elision seam in `django/db/models/sql/compiler.py`.
- `ORDERBY-003-S2`  
  Obligation: collapse duplicates only when direction and normalized body match.  
  Ownership: `get_order_by()` dedupe key construction and `seen` membership check in `django/db/models/sql/compiler.py`.
- `ORDERBY-003-S3`  
  Obligation: explicit `ASC` and default direction are semantically aligned (no semantic drift).  
  Ownership: direction-normalization rule in the same dedupe seam in `get_order_by()`, adjacent to existing `ORDERBY-002` normalization.

## Placement and ownership
- Primary owning seam: `SQLCompiler.get_order_by()` in `django/db/models/sql/compiler.py`.
  - Owns ordering-term de-duplication policy.
  - Owns `seen` key shape and duplicate decision.
  - Receives compiled SQL fragment, then decides whether each term reaches `result`.
- Supporting boundary:
  - `OrderBy`, `RawSQL`, and related expression classes provide compiled `sql` and `params`.
  - `_normalize_order_by_fragment_for_dedupe` provides formatting-normalized body content used by keys.
- Test boundary:
  - `tests/ordering/test_orderby_rawsql_trace.py` owns scenario coverage via `ORDERBY_003_REQUIREMENT_TO_TESTS`.

## Interface/type contracts
- Input contract at the seam: each term provides `(resolved_expr, is_ref)` from internal `order_by` list.
- Intermediate dedupe contract:
  - `direction_key = "DESC" if explicit DESC suffix exists, else "ASC"`.
  - `body_for_dedupe = <full normalized SQL fragment or fragment body as dictated by existing `ORDERBY-002` normalization flow>`.
  - `params_hash = make_hashable(params)`.
  - `dedupe_key = (body_for_dedupe, direction_key, params_hash)`.
- Output contract at seam:
  - `seen` stores dedupe tuples.
  - `result` only receives terms whose dedupe key is not already in `seen`.

## Dependency direction notes
- Dependency remains inward within `SQLCompiler`.
- `SQLCompiler.get_order_by()` depends on:
  - resolved expression metadata,
  - SQL compilation output,
  - deterministic regex-based direction extraction,
  - existing normalization helper and `make_hashable`.
- No new external modules should be introduced for this requirement.

## Integration seam / placeholders
- Concrete seam:
  - Between `sql, params = self.compile(resolved)` and `seen` lookup in `get_order_by()`.
  - Branch point:
    - if dedupe key exists: skip append (duplicate).
    - else: add key and append `(resolved, (sql, params, is_ref))`.
- Direction-semantics placeholder:
  - Explicit direction token must be part of the dedupe key.
  - Missing direction must default to `ASC` in keying logic (aligning explicit `ASC` and implicit direction semantics without changing rendering).

## Completion readiness
- Structural readiness is achieved when:
  - `ORDERBY-003` scenarios remain attached to the `get_order_by()` ownership boundary.
  - implementation comments or pseudocode in this seam are updated to include direction-aware dedupe keying.
  - the trace map and ADR form a coherent path from scenario IDs to implementation boundary.
