# ORDERBY-001 Architecture Decision Record

## Canonical requirement
- `ORDERBY-001`: In `SQLCompiler.get_order_by()`, deduplication for `ORDER BY` clauses must key on each term’s full SQL fragment (not only a trailing line slice), while normalizing multiline indentation so equivalent fragments dedupe correctly.

## Requirement-to-architecture map
- `ORDERBY-001-S1`  
  Owning surface: dedupe key construction in `SQLCompiler.get_order_by()`.  
  Structural effect: preserve all distinct `RawSQL` fragments in the emitted `result` list when their full normalized fragments differ.
- `ORDERBY-001-S2`  
  Owning surface: normalization contract for dedupe key generation.  
  Structural effect: canonicalize whitespace/line breaks across the full fragment before hashing.
- `ORDERBY-001-S3`  
  Owning surface: key equality boundary inside dedupe path.  
  Structural effect: duplicate collapse only when both `(normalized_full_fragment, make_hashable(params))` are equal.

## Component placement and ownership
- Primary owner: `SQLCompiler` in `django/db/models/sql/compiler.py` (`get_order_by()`).
  - Owns the duplicate-elision policy for compiled `ORDER BY` terms.
  - Owns the term de-duplication data structure (`seen`) and its key shape.
- Supporting boundary: expression/render layer (`expr`, `OrderBy`, `RawSQL`) supplies canonical SQL fragments.
  - No dedupe policy change here; only fragment text and params are consumed.
- Test boundary: `tests/ordering/test_orderby_rawsql_trace.py`.
  - Owns contract visibility through canonical IDs for scenarios S1-S3.

## Interface/type contracts
- `get_order_by()` output contract remains:
  - list of tuples `(expr, (sql, params, is_ref))`.
- Internal dedupe key contract (to be implemented in this boundary):
  - Key: `(normalized_full_fragment, make_hashable(params))`.
  - `normalized_full_fragment` derived from the fragment excluding ordering direction token while preserving full multiline body.
  - Must be deterministic for equivalent indentation and line-wrapping.
- Fallback contract: when fragment extraction fails, continue with the existing canonical raw-fragment fallback behavior.

## Dependency direction
- `compiler.py` depends on existing query/order context (`self.query`, `self.ordering_parts`) and existing `OrderBy`/`RawSQL` representations.
- Dedup key generation must not introduce new dependencies outward from `get_order_by()`; it remains internal to the compiler.

## Integration seams / placeholders
- Invariant seam for `ORDERBY-001`: section between `sql, params = self.compile(resolved)` and `result.append(...)`.
- Existing seam remains compatible with fallback extraction through:
  - `self.ordering_parts.search(sql)` for direction stripping and body extraction.
  - `params_hash = make_hashable(params)` for param-equivalence.
- Optional future seam: helper method for key normalization can be added to reduce complexity, but not required for implementation readiness.

## Readiness check
- Requirement coverage: all three scenarios mapped to compiler dedupe responsibility.
- Boundary integrity: SQL generation and dedupe selection remain within `SQLCompiler.get_order_by()` and tests own the scenario contract.
- Traceability preserved: requirement IDs are carried from canonical requirement through trace test map and this ADR.

