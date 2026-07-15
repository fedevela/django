# Architecture Artifact: Readonly `JSONField` Rendering in `display_for_field`

## Requirement-to-Architecture Map
- `D172-002`: `display_for_field` must preserve `JSONField.prepare_value` semantics for invalid input and must not bypass with direct serialization in this helper.
- `D172-003`: `display_for_field` must return the exact value produced by `JSONField.prepare_value` for subclassed fields, including subclass-specific formatting.

## Architectural Placement
- **Primary owner:** `django.contrib.admin.utils.display_for_field` in `django/contrib/admin/utils.py`.
- **Support owner:** `django.contrib.admin.utils.display_for_value` in the same module (type-agnostic formatter).
- **Boundary:** `display_for_field` is an admin-view utility; it must delegate field-specific normalization/serialization decisions to the field object (`prepare_value`) rather than own JSON conversion logic.

## Contracts / Interfaces
- **JSONField contract:** For readonly rendering, `display_for_field` must call `field.prepare_value(value)` when `field` is a `models.JSONField` instance.
- **Null contract:** Existing null/empty semantics remain before JSON-specific branch.
- **Output contract:** Render result is `display_for_value(prepared_value, empty_value_display)` where `prepared_value` is the exact return from `prepare_value`.
- **Negative invariant:** This admin helper does not apply `json.dumps` for this branch.

## Dependency Direction
- `display_for_field` depends on:
  - `models.JSONField` type check for branch selection.
  - `JSONField.prepare_value` (including subclass overrides) for transformation behavior.
- `JSONField` subclasses must not depend on admin utilities for `prepare_value` behavior.

## Integration Seam
- **Seam:** `display_for_field` JSONField branch.
  - **Ingress:** raw model/admin value.
  - **Transformation seam:** `prepare_value` override on the field instance.
  - **Egress:** `display_for_value` for presentation.

## Placement Rationale
- This preserves a single normalization point inside field instances, avoids admin-layer duplication, and prevents bypassing validation/normalization pathways for edge and invalid inputs.

## Traceability Targets
- Tests that should validate this structure and contracts:
  - `test_D172_002_display_for_field_jsonfield_invalid_input_uses_prepare_value`
  - `test_D172_003_display_for_field_jsonfield_subclass_prepare_value_exact_readonly_render_output`
