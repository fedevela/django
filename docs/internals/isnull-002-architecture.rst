ISNULL-002 Architecture Artifact
===============================

Requirement ID: ``ISNULL-002``

Goal
-----
Preserve existing ``__isnull=True`` / ``__isnull=False`` behavior for both direct
and related field lookups. The issue is architecture-only: place existing
obligation-specific logic so implementation can safely preserve SQL semantics and
row cardinality.

Requirement-to-architecture map
-------------------------------

1. ``ISNULL-002-s1`` -- direct nullable field lookups keep bool semantics:
   ``field__isnull=True`` maps to ``IS NULL``, ``field__isnull=False`` maps to
   ``IS NOT NULL``.
2. ``ISNULL-002-s2`` -- related field traversals keep the same contract:
   ``related__field__isnull=True/False`` remains ``IS NULL`` /
   ``IS NOT NULL`` with no changed join behavior.

Structural placement
--------------------

1. ``django/db/models/sql/query.py``:

   * Ownership boundary: ORM query-construction and resolution layer.
   * Responsibility: resolve lookup paths (direct and relation chains), keep a
     shared ``isnull`` branch, and avoid introducing path-specific SQL rewrites.
   * Integration seam: ``Query.build_lookup()`` remains the typed-input gate for
     constructing lookup objects; ``Query.build_filter()`` remains the common col
     and relation resolver before condition assembly.

2. ``django/db/models/lookups.py``:

   * Ownership boundary: SQL rendering for lookup operators.
   * Responsibility: document the rendering contract and keep ``IsNull.as_sql()``
     as a terminal bool-mapping sink.
   * Integration seam: ``IsNull.as_sql()`` emits the terminal predicate from
     already validated bool input only.

3. ``tests/lookup/tests.py`` and ``tests/null_queries/tests.py``:

   * Ownership boundary: scenario-level verification and regressions.
   * Responsibility: scenario IDs and baseline-equivalent behavior assertions for
     direct and related paths.
   * Integration seam: keep tests as explicit architecture trace points until
     runtime behavior parity is reintroduced.

Contract-level design
---------------------

- Contract domain: ``lookup_name == 'isnull'`` and RHS is ``bool``.
- Acceptance contract:
  - Direct and relation paths feed one lookup construction path.
  - ``rhs is True`` yields ``IS NULL`` at render.
  - ``rhs is False`` yields ``IS NOT NULL`` at render.
  - Existing query shape and cardinality decisions must remain intact for valid
    bool inputs.

Dependency direction
--------------------

1. Callers
   ``QuerySet.filter()/exclude()/Q`` -> ``Query.add_q()`` -> ``Query.build_filter()``.
2. Resolution
   ``Query.build_filter()`` -> ``Query.build_lookup()``.
3. Validation edge (existing)
   ``Query.build_lookup()`` decides bool-only acceptance and leaves bool values in the
   same constructor pipeline.
4. Rendering edge
   Valid ``IsNull`` lookups pass to ``IsNull.as_sql()`` with no operator or route
   branching by path type.

Traceability checklist
----------------------

1. ``ISNULL-002-s1`` maps to
   ``tests/lookup/tests.py::test_isnull_002_direct_nullable_field_preserves_true_false_semantics``
   and ``django/db/models/lookups.py:IsNull.as_sql``.
2. ``ISNULL-002-s2`` maps to
   ``tests/null_queries/tests.py::test_isnull_002_related_field_lookup_preserves_true_false_semantics``
   and ``django/db/models/sql/query.py:Query.build_filter`` / ``Query.build_lookup``.

Integration-ready skeletons
---------------------------

1. Keep ``Query.build_lookup()`` as the single entry point for ``isnull`` type
   control (bool-only entry into lookup construction).
2. Keep ``Query.build_filter()`` resolution branches path-agnostic for bool
   ``isnull`` predicates (direct field vs relation path should not alter operator
   choice).
3. Keep ``IsNull.as_sql()`` contract-only and explicit: bool ``True`` -> null
   predicate, bool ``False`` -> not-null predicate.
4. No changes required to join strategy from this issue: all existing join usage
   for valid bool lookups is preserved.

Readiness / completion status
-----------------------------

- Architecture artifact created: ``docs/internals/isnull-002-architecture.rst``.
- Requirement-to-architecture mapping complete for both traced obligations.
- Structural placement and dependency seams are explicit and implementation-ready.
