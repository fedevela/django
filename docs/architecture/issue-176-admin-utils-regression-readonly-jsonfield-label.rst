Issue #176 — Regression contracts for readonly JSONField display and label behavior
============================================================================

Context
-------
Requirement ID:
``D172-008``

This artifact captures the structural placement and integration boundaries for the
pseudocode obligations now represented in
``tests/admin_utils/tests.py``.

Requirement-to-architecture mapping
----------------------------------

- ``D172-008``: valid nested JSON readonly rendering behavior ->
  ``django.contrib.admin.utils.display_for_field`` readonly branch for
  ``isinstance(field, models.JSONField)`` in ``django/contrib/admin/utils.py``.
- ``D172-008``: invalid-input branch preservation ->
  ``django.contrib.admin.utils.display_for_field`` delegated to
  ``field.prepare_value`` contract (through JSONField method dispatch).
- ``D172-008``: unchanged non-JSON and ``label_for_field`` behavior ->
  non-JSON dispatch path in ``display_for_field`` and metadata-derived label
  derivation in ``django.contrib.admin.utils.label_for_field``.

File and ownership placement
----------------------------

Primary owners
~~~~~~~~~~~~~~
- ``django/contrib/admin/utils.py``
  owns conversion contracts for readonly values and labels:
  - ``display_for_field`` owns type-based output selection.
  - ``display_for_value`` owns shared non-JSON formatting helpers.
  - ``label_for_field`` owns metadata/form label derivation and return-shape rules.
- ``django/contrib/admin/helpers.py`` owns readonly field orchestration and invokes
  conversion/label contracts without adding formatting logic.
- ``tests/admin_utils/tests.py`` owns verification-only artifacts:
  - ``test_D172_008_display_for_field_jsonfield_nested_payload_uses_prepare_value_exact_render_text``
  - ``test_D172_008_display_for_field_jsonfield_invalid_input_preserves_prepare_value_contract``
  - ``test_D172_008_display_for_field_non_json_and_label_behavior_contracts_remain_unchanged``

Caller and boundary ownership
----------------------------

- ``helpers.AdminReadonlyField`` and related readonly consumers are the boundary
  where rendering context enters admin utilities.
- ``display_for_field`` and ``label_for_field`` remain pure consumers of already
  resolved model/form metadata and value inputs.

Integration seams
-----------------

1) Readonly rendering seam
   - Ingress: ``helpers.AdminReadonlyField`` and list display callsites pass
     ``(value, field, empty_value)`` to ``display_for_field``.
   - Egress: returned HTML/text is rendered directly by callers.
   - Responsibility: keep seam stable; JSON branching remains internal to
     ``display_for_field``.

2) JSON preparation seam
   - Ingress: ``display_for_field`` receives JSONField + payload.
   - Processing: one-way call to ``field.prepare_value(value)`` for truthy JSON and
     non-empty values.
   - Egress: exact returned string is emitted as readonly representation.
   - Non-functional constraint: invalid-input branch behavior must be owned by the
     field contract, not by fallback serialization logic.

3) Non-JSON fallback seam
   - Responsibility remains in ``display_for_value`` and the existing non-JSON
     branch chain (choices, boolean/date/number/file/generic).
   - Constraint: no coupling from JSON branch into this path.

4) Label seam
   - Ingress: model/form metadata and optional ``model_admin``/``form``.
   - Contract: ``label_for_field`` resolves label only; it must not inspect
     readonly display data.

Dependency direction
--------------------

- ``helpers`` depends on ``utils.display_for_field`` and ``utils.label_for_field``.
- ``utils.display_for_field`` depends on field type/runtime value contracts and
  delegates generic formatting to ``utils.display_for_value``.
- ``utils.label_for_field`` depends only on model metadata/form introspection and
  does not depend on display-specific JSON formatting state.

Architectural contracts to enforce
---------------------------------

- Contract A: JSON render must route through field-owned preparation and retain the
  exact return value (including nested payload ordering/escaping as produced by
  ``prepare_value``).
- Contract B: Invalid-input behavior in JSON mode must preserve the branch outcome
  defined by field-level ``prepare_value``.
- Contract C: Non-JSON rendering and label derivation contracts must remain
  unchanged and test-stable.
- Contract D: JSON and label pipelines stay independent across seams.

Readiness checklist
-------------------

- Requirement-to-architecture mapping exists for all three traced D172-008
  obligations.
- Ownership boundaries are explicit for ``utils`` (conversion/labels) and
  ``helpers`` (orchestration).
- Integration seams are contract-stable and one-way.
- Dependency direction is explicit and non-cyclic for the new coverage intent.
- One concrete architecture artifact has been added in ``docs/architecture``.
