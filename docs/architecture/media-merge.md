# Media JS merge architecture (MED-001..MED-003)

## Requirement-to-architecture map

- `MED-001` → `django/forms/widgets.py:Media._js` owns the merge orchestration entry point for `Media` objects; `media_property + media_property` integration path and `Widget.media` composition converge there.
- `MED-002` → `django/forms/widgets.py:Media.__add__` owns media-chain composition (sequence topology); `Media.merge()` owns deterministic constraint reconciliation for transitive satisfiable chains.
- `MED-003` → `django/forms/widgets.py:Media.merge()` owns de-duplication behavior, with `Media._js` enforcing single final emission.

## Module and boundary placement

- `forms/widgets.py` remains the owning module for form-media behavior.
- `Media` is the boundary owner for JS merge concerns.
- `Widget` and `Field` composition paths remain above this boundary and should only pass already-built media lists into `Media` seams, not apply ordering logic themselves.
- The merge boundary is internal to `Media.merge()` and not exported as a separate utility in this phase.

## Contracts and seams

- `Media._js` contract:
  - Input: ordered sequence `self._js_lists`.
  - Output: one deterministic script order list with constraint-valid ordering and duplicates suppressed in the final list.
  - Responsibility: apply `Media.merge()` in composition order and return final JS order only.
- `Media.__add__` seam contract:
  - Input: two `Media` objects.
  - Output: a combined `Media` container with concatenated `_js_lists` / `_css_lists`.
  - Responsibility: preserve merge sequence and avoid cross-sequence ordering semantics in the seam itself.
- `Media.merge(list_1, list_2)` contract:
  - Input: prior merged order (`list_1`) and next list (`list_2`).
  - State: `combined_list` and `last_insert_index`.
  - Output: merged order preserving constraints where satisfiable; conflict warning when inverse order is required.

## Dependency direction

- Composition direction: `Widget/Field` (producers) -> `Media` seam (`__add__`) -> `Media.merge()` and `Media._js` (resolver).
- Observation direction: `Media.render_js` reads `Media._js`.
- Constraint-warning direction: `Media.merge()` -> `MediaOrderConflictWarning`; callers remain passive.

## Integration-seam scaffolding

- Merge input seam: `Media.merge()` is the only algorithmic seam that mutates ordering state.
- Merge topology seam: `Media.__add__` aggregates candidates by append order and never performs ordering directly.
- Finalization seam: `Media._js` is the single finalizer before render path.

## Determinism and dedupe implementation plan (non-behavioral in this phase)

- Keep sequencing of list-1/list-2 merges as authored by `_js`.
- Enforce reverse traversal in `Media.merge()` to anchor frontier semantics for transitive constraints.
- Enforce insert-if-missing behavior in `Media.merge()` before insertion to guarantee dedupe-by-construction.
- Keep warning emission only when an element requires inversion relative to the current frontier.

## Readiness check (architecture)

- Every obligation MED-001..MED-003 has an owning locus and explicit seam.
- Dependency direction is explicit and acyclic for merge flow.
- There is a single concrete architecture artifact updated:
  - `docs/architecture/media-merge.md`
- Structural and traceable artifacts exist for implementation handoff to SPARC-L (logic + behavior changes).
