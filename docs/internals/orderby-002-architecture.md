# ORDERBY-002 Architecture Decision Record

## Canonical requirement
- `ORDERBY-002`: Normalize dedupe keys for ORDER BY fragments by canonicalizing line ending and line-break-adjacent spacing noise (`\r\n`, `\r`, `\n`, indentation/outer spacing) so equivalent multiline SQL maps to one duplicate key, while preserving SQL token meaning and excluding only direction-insensitive duplication.

## Requirement-to-architecture map
- `ORDERBY-002-S1`  
  Ownership pressure: canonicalization policy lives in the dedupe seam of `SQLCompiler.get_order_by()`.  
  Structural locus: in-memory dedupe key generation immediately after `sql, params = self.compile(resolved)`.
- `ORDERBY-002-S2`  
  Ownership pressure: whitespace normalization must target SQL-fragment formatting noise, not SQL token semantics.  
  Structural locus: helper contract between compiled fragment and `seen` key lookup.
- `ORDERBY-002-S3`  
  Ownership pressure: token-level differences must remain in final key comparison.  
  Structural locus: key tuple equality must still include both normalized SQL fragment and `make_hashable(params)`.

## Placement and ownership
- Primary owner: `SQLCompiler` in `django/db/models/sql/compiler.py`, inside `get_order_by()`.
  - Owns dedupe policy for ORDER BY terms and decides duplicate-elision behavior.
  - Owns the key normalization seam and the `seen` set contract.
- Supporting owner: existing query/expression layer (`OrderBy`, `RawSQL`, `Expr`) remains unchanged.
  - Provides already-compiled fragment and params; does not own normalization policy.
- Test-owner boundary: `tests/ordering/test_orderby_rawsql_trace.py`.
  - Owns scenario contracts for `ORDERBY-002` and maps scenario IDs to requirement assertions.

## Proposed interface/type contracts
- Deduplicated key shape (existing boundary, now explicit):  
  - `(normalized_sql_fragment, params_hash)`
  - `params_hash = make_hashable(params)`
- Proposed internal normalization contract (to be introduced in implementation):
  - Input: `compiled_sql_fragment: str`
  - Output: `normalized_fragment: str`
  - Guarantees:
    - Newline and carriage return variants collapse to a stable form.
    - Line-break-adjacent spacing and leading/trailing whitespace that represent visual formatting only are normalized deterministically.
    - Ordering token (`ASC|DESC`) can remain removed in the existing step upstream.
    - SQL token content (especially non-format content) remains unchanged for equality decisions.

## Dependency direction
- Direction remains inward to `SQLCompiler` internals:
  - `SQLCompiler.get_order_by()` reads outputs from expression resolution/compilation and emits `result`.
  - Normalization depends only on compiled SQL text and existing params.
  - No new external dependency is required before `ORDERBY-002` implementation.

## Integration seam / placeholders
- Concrete seam: inside `get_order_by()`, between
  - `sql, params = self.compile(resolved)` and
  - `seen` membership check.
- Existing implementation anchor remains the same; add/replace with an explicit normalization helper in the seam during next phase:
  - direction removal
  - line-ending normalization
  - whitespace noise normalization
  - tuple key construction

## Completion readiness
- All `ORDERBY-002` scenario pressures have an owning surface in `SQLCompiler.get_order_by()`.
- Requirement is traced through ADR + test trace file.
- No runtime behavior is required at this phase; the repository now has a concrete architecture artifact prepared for implementation.
