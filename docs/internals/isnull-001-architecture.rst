ISNULL-001 Architecture Artifact
===============================

Requirement ID: ``ISNULL-001``

Goal
-----
Place the deterministic ``__isnull`` RHS type enforcement logic into stable ORM
structure so all lookup construction paths fail early and deterministically on
non-``bool`` values.

Requirement-to-architecture map
-------------------------------

1. ``ISNULL-001-s1`` -- ``filter()``/``exclude()`` non-``bool`` RHS must raise
   ``FieldError`` immediately.
2. ``ISNULL-001-s2`` -- ``Q(...)`` non-``bool`` ``__isnull`` RHS must raise
   ``FieldError`` via the same deterministic path.
3. ``ISNULL-001-s3`` -- ``None`` and numeric inputs are also rejected for
   ``__isnull`` before SQL compilation or execution.

Structural placement
--------------------

1. ``django/db/models/sql/query.py``:

   * Ownership boundary: ORM query-construction layer (filter/exclude/Q input
     normalization, predicate materialization).
   * Responsibility: host the single early-validation gate for ``__isnull``
     RHS type.
   * Structural seam: ``Query.build_lookup()`` becomes the canonical choke point
     because all lookup construction routes are required to flow through it.

2. ``django/db/models/lookups.py``:

   * Ownership boundary: SQL rendering layer for lookup objects.
   * Responsibility: maintain render-only assumptions that only ``bool`` reaches
     ``IsNull.as_sql()``.
   * Structural seam: ``IsNull.as_sql()`` must remain a terminal consumer that does
     not broaden validation logic (it documents render contract only).

3. ``tests/lookup/tests.py`` and ``tests/queries/test_query.py``:

   * Ownership boundary: verification artifacts for regression surface area.
   * Responsibility: keep each requirement scenario mapped and isolated by
     scenario IDs.

Contract-level design
---------------------

- Contract token: ``lookup_name == 'isnull'`` and ``rhs must be bool``.
- Acceptance contract:

  * ``True``/``False`` values proceed to existing construction flow.
  * Any other type raises ``FieldError`` in construction path.
  * Validation occurs before SQL generation or execution is possible.

Dependency direction
--------------------

1. Caller path:

   ``QuerySet`` methods (``filter``/``exclude``) and ``Q`` trees delegate into
   ``Query.build_filter()``.
2. Unified query assembly:

   ``Query.build_filter()`` → ``Query.build_lookup()`` for each resolved lookup.
3. Validation edge:

   Validation decision in ``build_lookup()`` blocks invalid ``isnull`` RHS and
   therefore prevents downstream SQL renderer invocation.
4. Rendering:

   Valid ``IsNull`` lookup objects reach ``IsNull.as_sql()`` unchanged.

Traceability checklist
----------------------

1. ``ISNULL-001-s1`` maps to
   ``tests/lookup/tests.py::test_isnull_001_filter_and_exclude_nonbool_rhs_raises_fielderror``
   and to ``django/db/models/sql/query.py:Query.build_lookup``.
2. ``ISNULL-001-s2`` maps to
   ``tests/queries/test_query.py::test_isnull_001_q_lookup_nonbool_rhs_raises_fielderror_early``
   and to ``django/db/models/sql/query.py:Query.build_filter`` /
   ``Query.build_lookup``.
3. ``ISNULL-001-s3`` maps to
   ``tests/lookup/tests.py::test_isnull_001_none_and_numeric_rhs_must_raise_fielderror``
   and to ``django/db/models/sql/query.py:Query.build_lookup``.

Integration-ready skeletons
---------------------------

1. Implement validation in ``Query.build_lookup()`` as a single branch keyed by
   ``lookup_name == 'isnull'``.
2. Keep ``IsNull.as_sql()`` in ``lookups.py`` as the post-validated render sink.
3. Ensure no alternate construction path bypasses ``build_lookup()`` for ``__isnull``.

