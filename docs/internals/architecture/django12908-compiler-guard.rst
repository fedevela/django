DJANGO12908 ORM Compilation Architecture
=======================================

This document maps the deterministic ORM-combinator guard logic to a concrete architectural placement.

Requirement-to-architecture map
-------------------------------

- DJANGO12908-001
  - Architectural pressure: compile-time failure contract for explicit ``distinct(...)`` over annotated ``union()`` queries.
  - Home: preflight branch in ``SQLCompiler.as_sql()`` before combinator SQL generation.
- DJANGO12908-004
  - Architectural pressure: narrow scope to only annotated ``union`` with explicit-field distinct.
  - Home: conditional guard using ``combinator == 'union'``, ``query.distinct_fields``, and ``query.annotation_select``.
- DJANGO12908-005
  - Architectural pressure: keep projection schema stable and do not mutate annotations/selected columns.
  - Home: guard path that raises before projection manipulation.
- DJANGO12908-008
  - Architectural pressure: keep change inside compiler/query path only.
  - Home: ``django.db.models.sql.compiler``; no query API/model/schema/contracts are edited.

File/module placement and ownership
----------------------------------

- Primary owner: ``django/db/models/sql/compiler.py``
  - Function: ``SQLCompiler.as_sql``.
  - Responsibility: compound-query compilation and SQL emission.
- Supporting state holder: query object attributes in ``django/db/models/sql/query.py``
  - ``query.combinator`` identifies ``union``/``difference``/``intersection`` flow.
  - ``query.distinct_fields`` indicates explicit ``distinct('field', ...)``.
  - ``query.annotation_select`` indicates active annotation projection.
- Test locus: ``tests/queries/test_qs_combinators.py``
  - Existing requirement traceability comments and dedicated DJANGO12908 tests remain as verification anchors.

Boundary and dependency rules
----------------------------

- Dependency direction is strict:
  - Query construction mutates ``query`` state.
  - Compiler reads state and decides whether the compound path is legal.
  - Backend feature flags gate generic support.
- The guard remains in compiler space and must not cross into QuerySet methods, model layer, or API surfaces.

Integration seam and contract
----------------------------

- Integration seam: ``if combinator:`` branch in ``SQLCompiler.as_sql``.
- Contract for rejection:
  1. Evaluate only when ``combinator`` is truthy.
  2. Apply guard only when ``combinator == 'union'``.
  3. Apply guard only when ``query.distinct_fields`` is non-empty.
  4. Apply guard only when ``query.annotation_select`` is non-empty.
  5. Raise ``NotSupportedError`` with a deterministic unsupported-operation message before calling ``get_combinator_sql``.
- For all other paths (non-``union``, ``union`` without explicit distinct fields, non-annotated compound queries), preserve current behavior.

Dependency-direction notes
-------------------------

- No new modules are introduced.
- No changes are made to model/schema/API contracts.
- Backend-specific behavior remains behind existing feature flags.

Open structural placeholders
---------------------------

- Placeholder remains in code comments in ``compiler.py`` marking the guard seam.
- Future implementation phase should replace the placeholder with executable rejection logic and add regression tests that assert raised exceptions.

Completion status
----------------

- All four requirements are mapped to compiler-level ownership and seams.
- Repository includes one architecture artifact update and one owning module comment update.
- Structural readiness: compiler seam, interfaces, boundaries, and narrow-scope dependencies are explicitly documented.
