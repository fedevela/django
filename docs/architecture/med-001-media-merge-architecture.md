# Architecture Artifact — MED-001

## Requirement-to-architecture map

- `MED-001` (Scenario 1): `ColorPicker`, `SimpleTextWidget`, `FancyTextWidget` in `MyForm` must merge to dependency-valid JS order equivalent to `['text-editor.js', 'text-editor-extras.js', 'color-picker.js']` with no `MediaOrderConflictWarning`.
- `MED-001` (Scenario 2): repeated `MyForm().media` access on identical composition must keep JS sequence and warning count stable.

Test traceability anchors:
- `tests/forms_tests/tests/test_media.py` `FormsMediaMergeContractTests.requirement_map`
- Scenario 1 method:
  `test_med_001_scenario_1_colorpicker_simpletext_fancytext_myform_media_resolves_dependency_valid_sequence_without_warning`
- Scenario 2 method:
  `test_med_001_scenario_2_repeated_media_access_is_stable_for_identical_three_way_form_composition`

## Placement and ownership

1. Dependency merge primitive:
   - File: `django/forms/widgets.py`
   - Owner: `Media.merge(list_1, list_2)`
   - Responsibility: reconcile two ordered lists into one deterministic sequence.

2. Class/media declaration ownership:
   - File: `django/forms/widgets.py`
   - Owner: `media_property(cls)` and `MediaDefiningClass`
   - Responsibility: define how class-level media is resolved, extended, and inherited.

3. Widget-level boundary and composition:
   - File: `django/forms/widgets.py`
   - Owner: `Widget._get_media` and `MultiWidget._get_media`
   - Responsibility: reduce widget and subwidget media into a single ordered `Media` value.

4. Form-level aggregation boundary:
   - File: `django/forms/forms.py`
   - Owner: `BaseForm.media` property
   - Responsibility: aggregate all field widget media in declaration order for the form.

## Architectural contracts (structural)

- `IMediaSequence` contract (implicit)
  - Input: immutable media lists (`_js`, `_css` slices)
  - Output: ordered list with deterministic insertion constraints satisfied by `Media.merge`
  - Guarantee: preserves explicit relative order wherever it is not contradictory.

- `IMediaPrecedence` contract
  - Input: inheritance media chain + optional `class Media(extend=...)`
  - Output: resolved base media followed by local class media.
  - Direction: parent class first, current class later.

- `IMediaHost` contract
  - Input: ordered source list of fields/widgets/subwidgets.
  - Output: stable single `Media` aggregate; no mutation of source media objects.

## Dependency direction and integration seams

- Direction:
  `base class Media` -> `media_property` -> `Widget.media` -> `Field.widget.media` -> `BaseForm.media`

- Seams:
  - Seam A: `media_property` (class declaration seam between inheritance and declaration).
  - Seam B: `Media.merge` (cross-list dependency reconciliation seam).
  - Seam C: `Widget._get_media` (instance composition seam between widget and subwidget media).
  - Seam D: `BaseForm.media` (form-level aggregation seam across fields).

- Anti-regression boundary:
  - No API additions/renames.
  - No changes to public widget registration mechanisms.

## Stability and repeatability boundary

- `MED-001` Scenario 2 requires that property access remains pure:
  same composition sequence must produce identical merge graph traversal and warning behavior each call.
- Therefore, merges must remain order-driven by deterministic loops over ordered field/widget lists.

## Minimal implementation-ready structure

No code-path behavior changes are introduced in this artifact.
The implementation surface is complete if these boundaries and contracts are enforced in:
- `Media.merge` and `Media.merge` callers,
- `media_property` / inheritance logic,
- `BaseForm.media` and `MultiWidget._get_media` composition order.
