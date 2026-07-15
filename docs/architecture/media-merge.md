# Media JS merge architecture (MED-001..MED-007)

## Requirement-to-architecture map

- `MED-001` → `django/forms/widgets.py:Media._js` owns merge orchestration entry point for `Media` objects; `media_property` and `Widget.media` composition converge there.
- `MED-002` → `django/forms/widgets.py:Media.__add__` owns media-chain composition ordering; `Media.merge()` owns deterministic reconciliation for satisfiable transitive relations.
- `MED-003` → `django/forms/widgets.py:Media.merge()` and `Media._js` own deduplication control (per-list and final frontier).
- `MED-004` → `django/forms/widgets.py:Media.merge()` owns irreconcilable-order detection; warnings are emitted only for true cycles and only with directly participating file pair payload.
  - Trace anchors in tests:
    - `test_med_004_emit_media_order_conflict_warning_only_for_irreconcilable_js_relations`
    - `test_med_004_no_conflict_warning_when_js_constraints_are_satisfiable`
- `MED-007` → `django/forms/widgets.py:Media.merge()` + `Media._js` own usable-result guarantee under conflict, with warning as explicit unresolved-order signal and no merge abort.
  - Trace anchors in tests:
    - `test_med_007_merge_returns_usable_media_on_true_js_conflict`
    - `test_med_007_merge_warns_on_conflict_but_preserves_deduplicated_css_js`

## Architecture pressures (SEFIRAH framing)

- Ownership pressure:
  - Keep JS ordering behavior localized in `Media` class (`forms/widgets.py`); no additional cross-module media-order service in this phase.
- Boundary pressure:
  - `Media` is the exclusive boundary for order constraints and conflict classification.
  - `Widget`, `Field`, and `Form` call stacks pass built media objects and do not impose JS precedence.
- Contract pressure:
  - `__add__` only composes candidate lists.
  - `_js` performs finalization by replaying composed lists through `merge()`.
  - `merge()` applies constraint reconciliation and returns a frontier list.
  - `MediaOrderConflictWarning` remains side-effect output from `merge()` only.
- Dependency direction pressure:
  - `Widget/Field/Form` → `Media.__add__` → `Media._js`/`merge()` → `MediaOrderConflictWarning`.
  - `Media` render methods consume merged results; they do not participate in ordering decisions.

## Interface / placement decisions

- `Media._js`:
  - Input: ordered tuple/list of JS definitions from `_js_lists`.
  - Output: merged JS list.
  - Responsibility: final frontier assembly and deterministic serialization precondition.
- `Media.__add__`:
  - Input: two `Media` instances.
  - Output: combined candidate lists preserving declaration sequence.
  - Responsibility: topology capture and hand-off.
- `Media.merge(list_1, list_2)`:
  - Input: frontier list and next list.
  - Output: merged frontier list + optional one-shot conflict warning.
  - Rule set:
    - Build/maintain relative constraints from list adjacency (`left` must precede `right`).
    - Permit satisfiable constraints; emit warning only when irreconcilable.
    - Warning payload must be `[left, right]` or equivalent representing the direct conflicting relation only.
    - Return frontier regardless of warning so renderability is preserved.
- `MediaOrderConflictWarning`:
  - Emission point: `Media.merge`.
  - Fan-out: caller-only passive receiver; no merge consumers catch-and-resolve.
  - Emission cardinality: at most once per merge operation.

## Integration seams and scaffolding

- Merge topology seam: `Media.__add__` appends candidate lists only; no ordering logic there.
- Constraint seam: `Media.merge` is the only local point that mutates frontier state for ordering.
- Finalization seam: `Media._js` is the sole ordered replay point before render serialization.
- Warning seam: `Media.merge` owns direct conflict detection and warning dispatch with no propagation to rendering code.

## Readiness check (SEFIRAH-09 architecture completion)

- Each traced obligation has a mapped owner and explicit contract:
  - MED-004: owned by `Media.merge`, boundary-local conflict classification and payload shaping.
  - MED-007: owned by `Media.merge` + `_js`, fallback usability contract.
- The required contract artifacts are now explicit and traceable:
  - `docs/architecture/media-merge.md`
  - `tests/forms_tests/tests/test_media.py` (`FormsMediaTraceabilityTests.REQUIREMENT_TO_TEST`)
- Dependency direction is explicit, acyclic for normal flow, and preserves current public API (`media1 + media2`).
