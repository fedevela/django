# Architecture Artifact: Decouple `label_for_field` from readonly JSON formatting

## Canonical Requirement
- ``D172-007``
  - ``label_for_field`` must remain metadata-driven and unchanged by JSON readonly rendering behavior.

## Requirement-to-Architecture Map
- ``D172-007`` -> ``django.contrib.admin.utils.label_for_field``
  - label source resolution from model/field metadata and fallback metadata lookup.
- ``D172-007`` -> ``django.contrib.admin.helpers.AdminReadonlyField``
  - maintain sequencing: label materialization before value rendering.
- ``D172-007`` -> ``django.contrib.admin.helpers.InlineAdminFormSet.fields``
  - keep inline-readonly label path metadata-first and separate from value formatting.

## Topology and ownership

Primary owners
- ``django.contrib.admin.utils``: ``label_for_field`` owns label derivation contract.
- ``django.contrib.admin.helpers``: ``AdminReadonlyField`` and inline field metadata assembly own when/where labels are read in readonly UI codepaths.

Explicit boundaries
- Label boundary:
  - Input: ``name``, ``model``, optional ``model_admin``, optional ``form``.
  - Output: label string (and optional attribute).
  - Must not read value-formatting state.
- Value boundary:
  - Input: resolved field/value/admin-empty marker.
  - Output: rendered display string from ``display_for_field``.
  - Must not alter label selection.

## Contracts (stability obligations)

1. ``label_for_field`` contract
- Resolve labels from model/field metadata and fallback attribute metadata.
- ``return_attr`` only changes returned tuple shape.
- No dependency on JSON serialization, ``display_for_field``, or readonly value branches.

2. ``AdminReadonlyField`` contract
- Resolve label prior to value path in ``__init__``.
- Resolve value path in ``contents`` via ``display_for_field`` only.
- Keep label and value branches independent.

3. ``InlineAdminFormSet.fields`` contract
- For readonly inline fields, derive ``label`` from ``meta_labels`` fallback to ``label_for_field``.
- Do not route JSON/readonly formatting decisions into label assembly logic.

## Dependency-direction notes
- ``label_for_field`` depends on:
  - model metadata and fallback introspection helpers.
- ``display_for_field``/JSON field rendering logic depends on:
  - field type and field/value transformation.
- Direction is one-way into helpers: helper components consume both outputs as values, but do not invert dependency.

## Integration seams
- Label seam (ingress/egress):
  - ``helpers`` reads label via ``label_for_field`` or explicit metadata map;
  - returns display label for templates/forms.
- Value seam (ingress/egress):
  - ``helpers`` passes raw value to ``display_for_field``;
  - receives rendered readonly representation.
- No edge from value seam back into label seam.

## Negative invariants
- Do not add label coupling to JSON readonly branches.
- Do not convert `label_for_field` into a display-value formatter.

## Traceability targets
- ``tests/admin_utils/tests.py``
  - ``test_D172_007_label_for_field_metadata_derivation_remains_decoupled_from_readonly_jsonpath``
  - ``test_D172_007_label_for_field_and_readonly_json_rendering_remain_separable_contracts``
