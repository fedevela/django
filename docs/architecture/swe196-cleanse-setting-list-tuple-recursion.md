# Architecture Artifact: Issue #198 — Recursive list/tuple sanitization for safe settings

## Requirement mapping

`SWE196-002` — Recursively process nested `list` and `tuple` values so sensitive entries inside iterable paths are reachable.
`SWE196-006` — Preserve container type (`list` stays `list`, `tuple` stays `tuple`) and keep element order.
`SWE196-005` — Preserve scalar elements exactly (order and value) while masking only dict keys that match sensitive patterns.

## Architectural locus and ownership

Primary owner: `django.views.debug.SafeExceptionReporterFilter`.

Primary recursion entry points:
- `SafeExceptionReporterFilter.get_safe_settings()`
- `SafeExceptionReporterFilter.get_safe_request_meta()`

Both call `SafeExceptionReporterFilter.cleanse_setting(key, value)` and are the only public
paths entering the issue’s sanitization boundary during this phase.

## Traceability to verification artifacts

Requirement to test mapping is encoded in:
- `tests/view_tests/tests/test_debug.py` (within `SafeExceptionReporterFilterTests.contract_verification_map`)
- `test_guid_swe196_002_list_tuple_recursion_reaches_sensitive_dict_keys`
- `test_guid_swe196_006_iterable_shape_is_preserved_for_list_and_tuple`
- `test_guid_swe196_005_iterable_scalars_are_preserved_and_unchanged`

## Responsibility split (placement and boundaries)

`cleanse_setting` owns traversal and transformation policy for a single setting value.

`get_safe_settings` owns enumeration of uppercase settings and delegates every value to
`cleanse_setting`.

`get_safe_request_meta` owns request-meta enumeration and delegates every value to
`cleansing_setting`.

No other module owns sanitization behavior for nested iterables in this phase.

## Interface / contract boundary

`cleanse_setting(key, value)` contract:
- Input:
  - `key` string-like identifier for current node.
  - `value` arbitrary runtime object.
- Output:
  - Sanitized object with same top-level container identity for supported traversable types in this scope.
- Error boundary:
  - `TypeError` from regex matching must leave the current node unchanged.

Supported traversal nodes:
- `dict`: create a new dict and recurse per key/value pair.
- `list`: create a new list and recurse per index in order.
- `tuple`: create a new tuple and recurse per index in order.
- scalar / non-`dict`/`list`/`tuple`: return as-is.

## Dependency direction

Direction is inward and value-shape driven:

1. `get_safe_settings` / `get_safe_request_meta` → `cleanse_setting`.
2. `cleanse_setting` (parent key) → `cleanse_setting` (child key/value pairs and child elements).
3. Sanitized value returns to caller; no outbound dependencies for recursive result materialization.

Sensitive-key pattern matching remains local via `SafeExceptionReporterFilter.hidden_settings`.

## Structural pressure decomposition

`SWE196-002` pressure:
- recursive reachability into nested list/tuple elements.
- boundary: recursion is allowed only for list/tuple/dict value nodes, no generic iterable expansion.

`SWE196-006` pressure:
- immutable container-shape guarantee.
- boundary: type reconstruction per container kind at each recursion return boundary.

`SWE196-005` pressure:
- scalar preservation policy.
- boundary: scalar pass-through branch before any reconstruction or mutation.

## Proposed integration seam (staging)

No new modules are required now. If implementation phase needs explicit seam points,
add private helpers in the same module only:
- `_iterable_cleanse_elements(value)` — ordered element iterator + recursive dispatch.
- `_sanitize_scalar_or_container(value)` — explicit scalar fallback.

This preserves module locality and avoids expanding dependencies outside
`django.views.debug` while keeping recursion direction and contracts explicit.

