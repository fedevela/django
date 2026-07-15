# ORDERBY-006 Architecture Decision Record

## Canonical requirement
- `ORDERBY-006` [ORANGE]: Treat Unicode content as opaque SQL text during normalization and keying, changing only whitespace/newline-normalization behavior, so deduplication remains stable without corrupting query text.

## Requirement-to-architecture map
- `ORDERBY-006-S1`  
  - Canonical pressure: preserve Unicode query text in the emitted SQL after dedupe normalization.
  - Structural home: dedupe-key generation lane in `django/db/models/sql/compiler.py:SQLCompiler.get_order_by()` immediately after `sql, params = self.compile(resolved)`.
  - Mapping: the raw rendered SQL fragment and params remain paired as `(sql, params)` for output; normalization only affects the `without_ordering` branch used for `dedupe_key`.
- `ORDERBY-006-S2`  
  - Canonical pressure: dedupe should be based on non-whitespace body semantic equivalence and direction alignment.
  - Structural home: same `get_order_by()` seam using `dedupe_key = (without_ordering, direction_key, params_hash)` where `without_ordering` is normalized for line/space noise.
  - Mapping: semantically equivalent line-ending variants map to equal normalized bodies; non-equivalent content must remain distinct unless full key tuple matches.
- `ORDERBY-006-S3`  
  - Canonical pressure: mixed spacing and line-ending variants must yield stable duplicate decisions while preserving non-whitespace bytes.
  - Structural home: `_normalize_order_by_fragment_for_dedupe()` in `django/db/models/sql/compiler.py`.
  - Mapping: this helper owns deterministic state-machine normalization and is the only location expected to alter fragment bytes for dedupe.

## Placement and ownership
- Primary owner: `SQLCompiler.get_order_by()` in `django/db/models/sql/compiler.py`.
  - Owns dedupe policy for all ordering fragments entering ORDER BY.
  - Owns direction-state selection (`direction_match` path vs malformed fallback lane).
  - Owns the `seen` set and the decision to emit or suppress duplicates.
- Supporting owner: `SQLCompiler._normalize_order_by_fragment_for_dedupe()`.
  - Owns formatting canonicalization for dedupe-only body text.
  - Must remain side-effect free and only normalize structural whitespace/newline patterns.
- Test boundary owner: `tests/ordering/test_orderby_rawsql_trace.py`.
  - Owns acceptance scenarios for `ORDERBY-006`.

## Interface/type contracts
- Seam contract for keying:
  - Input: compiled fragment `(sql, params)` and regex-derived direction state.
  - Process:
    - detect direction token using existing suffix parsing path;
    - remove/mark direction using existing `direction_key` semantics;
    - run body through `_normalize_order_by_fragment_for_dedupe()`;
    - compute `params_hash = make_hashable(params)`;
    - build `dedupe_key = (normalized_body, direction_key, params_hash)`.
  - Output: `if dedupe_key in seen: skip`; else append `(resolved, (sql, params, is_ref))`.
- Canonicalization contract for `_normalize_order_by_fragment_for_dedupe(sql)`:
  - Input: string fragment.
  - Output: deterministic string differing only by allowed line-break and inter-token whitespace reduction.
  - Non-negotiable invariants:
    - do not Unicode case-fold, transliterate, escape, or re-encode payload bytes;
    - preserve non-whitespace body content byte shape (including non-ASCII characters);
    - keep quote-state handling deterministic for quote boundaries while applying whitespace state transitions outside quoted regions.
- Boundary seam contract:
  - `direction_key` is part of the key tuple and must not be omitted during fallback.
  - `without_ordering` is key-only; `sql` preserves rendering output for emission.

## Dependency direction
- `get_order_by()` depends inward on:
  - expression resolution output (`resolve_expression`);
  - SQL rendering (`compile`);
  - existing regex direction path;
  - `_normalize_order_by_fragment_for_dedupe`;
  - `make_hashable`.
- `_normalize_order_by_fragment_for_dedupe()` depends only on fragment text, local whitespace state tracking, and existing string semantics.
- No new cross-module dependencies are introduced.

## Integration seams and stubs
- Concrete seam:
  - between `sql, params = self.compile(resolved)` and `dedupe_key` computation in `get_order_by()`.
  - between `without_ordering` payload and `_normalize_order_by_fragment_for_dedupe(without_ordering)` in that seam.
- Structural guardrails:
  - direction parsing failure must still follow deterministic fallback into `dedupe_key` construction.
  - dedupe may only depend on `normalized_body`, `direction_key`, and `params_hash`.
  - normalization helper must keep Unicode payload opaque.

## Completion status
- `ORDERBY-006` mapped to owning runtime seams and test boundary.
- Requirement traceability now added in this concrete ADR.
- No runtime behavior changes in this phase.
