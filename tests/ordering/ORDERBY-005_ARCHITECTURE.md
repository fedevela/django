# ORDERBY-005 architecture artifact

Status: `READY_FOR_IMPLEMENTATION`
Owner: `Sefirah 09 (Architecture)`
Traceability root: `ORDERBY-005`

## Requirement-to-architecture map

- `ORDERBY-005-S1`: malformed or irregular direction text must not be dropped in dedupe.
  - Architecture pressure: deterministic fallback lane before dedupe key generation.
  - Structural home: `django/db/models/sql/compiler.py::SQLCompiler.get_order_by()`.
  - Mapping point: `direction_match` / `direction_key` decision branch.
- `ORDERBY-005-S2`: duplicate malformed terms dedupe to a single emission.
  - Architecture pressure: canonical fallback keying into the `seen` duplicate set.
  - Structural home: `django/db/models/sql/compiler.py::SQLCompiler.get_order_by()` loop.
  - Mapping point: `dedupe_key = (...)` and `if dedupe_key in seen`.
- `ORDERBY-005-S3`: malformed and parseable equivalent forms must not collide accidentally.
  - Architecture pressure: stable lane separation by parse outcome in key material.
  - Structural home: key-shape decision in `get_order_by()` before `seen` insertion.
  - Mapping point: `direction_key` value source in normal vs fallback path.

## File/module placement decisions

- Keep responsibility for fragment rendering and dedupe policy in `SQLCompiler.get_order_by`:
  - It already owns ORDER BY assembly and duplicate filtering.
  - It already owns normalization utilities (`_normalize_order_by_fragment_for_dedupe`) used by dedupe.
- Keep malformed-lane verification in trace suite only:
  - `tests/ordering/test_orderby_rawsql_trace.py` already hosts `ORDERBY-005` placeholder assertions.
  - Existing placeholder tests map to this requirement and remain the acceptance frontier.

## Ownership boundaries

- `SQLCompiler.get_order_by` boundary:
  - Inputs: compiled `expr` item pairs and `compile` output `(sql, params)`.
  - Outputs: ordered `result` entries and dedupe state transition on `seen`.
  - Invariant to preserve: no ORDER BY fragment may be removed before duplicate checking.
- `_normalize_order_by_fragment_for_dedupe` boundary:
  - Internal helper for canonicalizing only whitespace and line-break noise.
  - Must remain side-effect free and string-only.

## Structural contract (next-implementation-ready)

- `order_by_dedupe_key = (normalized_fragment, direction_signature, params_hash)` is the ownership contract for duplicate filtering.
- `direction_signature` must encode parse outcome deterministically:
  - `"ASC"`/`"DESC"` for parsed, normalized directions.
  - Fallback signature for malformed fragments must be stable across identical inputs.
- `seen` contains one entry per emitted key:
  - If key already exists, skip emission.
  - Else append to `result` and record key.
- `params_hash` must remain hashable and scoped per fragment input.

## Dependency-direction notes

- `compiler.py` (runtime) depends on:
  - `compile` output from expression resolution path.
  - `re.search` parsing path for direction extraction.
  - `_normalize_order_by_fragment_for_dedupe`.
  - `make_hashable`.
- Traceability tests depend on runtime behavior via query string output assertions, but do not own dedupe internals.
- No external module dependencies are added for `ORDERBY-005`; direction parsing and normalization remain in the same module.

## Integration seams and stubs

- Seams:
  - `get_order_by`: decision seam for parse-vs-fallback route.
  - duplicate filter (`seen` + `dedupe_key`) seam for deterministic emission control.
- Planned structural stub (no runtime change in this phase):
  - Add explicit `ORDERBY-005` lane comment contract in `get_order_by` documenting fallback-signature invariants.

## Completion status (SEFIRAH 09)

- All three traced obligations mapped to concrete loci.
- Boundary and dependency ownership made explicit.
- One architecture artifact created and implementation-ready.
