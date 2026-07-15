Issue #173 — Read-only JSONField rendering in ``display_for_field``
================================================================

Context
-------
Requirement IDs:
``D172-001``, ``D172-004``, ``D172-005``, ``D172-006``.

This artifact captures the structural placement and interfaces for the next
implementation phase.

Requirement-to-architecture mapping
----------------------------------

- ``D172-001`` -> function ``display_for_field`` in ``django/contrib/admin/utils.py`` (read-only rendering branch for JSONField).
- ``D172-004`` -> null/empty handling branch in ``display_for_field`` and existing tests that assert empty/null behavior in ``tests/admin_utils/tests.py``.
- ``D172-005`` -> type-guard decision point in ``display_for_field`` using ``isinstance(field, models.JSONField)``.
- ``D172-006`` -> all existing formatting helper calls via ``display_for_value`` and non-JSON branches in ``display_for_field``.

Placement and ownership
-----------------------

Primary owning module
~~~~~~~~~~~~~~~~~~~~~
- ``django/contrib/admin/utils.py`` owns display rendering behavior for admin readonly fields.

Caller boundary ownership
~~~~~~~~~~~~~~~~~~~~~~~~
- ``django/contrib/admin/templatetags/admin_list.py`` and
  ``django/contrib/admin/helpers.py`` own template/control orchestration and
  consume values from ``display_for_field``; they do not implement type-specific
  formatting.

Seams and integration points
----------------------------

1) Read-only field rendering seam
   - Entry: ``admin_list.py`` and ``helpers.py`` call
     ``display_for_field(value, field, empty_value_display)``.
   - Exit: function returns string/markup for rendering.
   - Responsibility: keep this seam stable; only update conversion semantics inside
     ``display_for_field``.

2) Value formatting seam
   - ``display_for_field`` delegates generic conversion to
     ``display_for_value``.
   - Responsibility boundary: generic fallback remains in ``display_for_value`` and
     must stay unchanged for non-JSON behavior.

Dependency direction
--------------------

- ``admin_list/helpers -> utils.display_for_field -> utils.display_for_value``.
- ``display_for_field`` depends on ``models.JSONField`` type checks and existing admin
  helpers (``_boolean_icon``, ``formats``, ``timezone``).
- No new outward dependency from admin rendering callsites into models or storage
  layers is introduced.

Architectural contracts
-----------------------

- Contract A (JSON only): JSON-specific readonly formatting logic must only apply when
  the exact input ``field`` is an instance of ``models.JSONField``.
- Contract B (empty/null preservation): empty/null handling remains first-class and
  continues to use ``empty_value_display`` semantics before any JSON preparation.
- Contract C (non-JSON stability): non-JSON branches must preserve existing order and
  behavior (choices, boolean, datetime, number, file, generic fallback).
- Contract D (helper boundary): ``display_for_value`` continues to be field-agnostic and
  is not extended with JSON-only rendering logic.

Adapter / implementation stubs to keep
--------------------------------------

- ``display_for_field`` branch map remains:
  - flatchoices -> boolean -> null -> datetime/date/time -> numbers -> file -> json branch -> fallback.
- JSON branch can be implemented in this order, guarded by ``isinstance(field, models.JSONField)``.
- Fallback to ``display_for_value`` remains unchanged in signature and behavior.

Topology and files to touch
---------------------------

- ``django/contrib/admin/utils.py``
  - Add or activate JSON-only readonly branch for ``field.prepare_value`` in
    ``display_for_field`` without perturbing non-JSON flow.
  - Keep ``display_for_value`` unchanged as a shared helper.
- ``tests/admin_utils/tests.py``
  - Implement the four placeholder tests that already map to D172 requirements.
  - Preserve and reuse existing non-JSON regression tests for ``D172-006`` and ``D172-004`` cross-checks.

Readiness check
---------------

- Every traced requirement has an owning locus in this artifact.
- There is one concrete architecture artifact added in ``docs/architecture``.
- Ownership boundaries and dependency direction are explicit and implementation-ready.
