DJANGO12908 ORM Compilation Architecture
=======================================

This document maps the deterministic ORM-combinator guard logic to a concrete architectural placement.

Requirement-to-architecture map
-------------------------------

- DJANGO12908-001
  - Architectural pressure: compile-time failure contract for explicit ``distinct(...)`` over annotated ``union()`` queries.
  - Home: preflight branch in ``SQLCompiler.as_sql()`` before combinator SQL generation.
- DJANGO12908-002
  - Architectural pressure: deterministic failure contract must hold for all evaluation entry points.
  - Home: the same compiler seam (`SQLCompiler.as_sql()`) must execute before every compound SQL emission path used by
    ``QuerySet`` evaluation APIs (`count`, `exists`, `__iter__/list`).
- DJANGO12908-004
  - Architectural pressure: narrow scope to only annotated ``union`` with explicit-field distinct.
  - Home: conditional guard using ``combinator == 'union'``, ``query.distinct_fields``, and ``query.annotation_select``.
- DJANGO12908-005
  - Architectural pressure: keep projection schema stable and do not mutate annotations/selected columns.
  - Home: guard path that raises before projection manipulation.
- DJANGO12908-003
  - Architectural pressure: the failure contract must expose a stable class/message pair.
  - Home: deterministic raise site in ``SQLCompiler.as_sql()`` using ``NotSupportedError`` and fixed message
    ``"annotate() + union() + distinct(fields) is not supported."``.
- DJANGO12908-008
  - Architectural pressure: keep change inside compiler/query path only.
  - Home: ``django.db.models.sql.compiler``; no query API/model/schema/contracts are edited.
- DJANGO12908-007
  - Architectural pressure: regression verification must assert explicit unsupported-operation path, never row-count success.
  - Home: ``tests/queries/test_qs_combinators.py`` with contract-driven expectation around ``compound.count()``.

File/module placement and ownership
----------------------------------

- Primary owner: ``django/db/models/sql/compiler.py``
  - Function: ``SQLCompiler.as_sql``.
  - Responsibility: compound-query compilation and SQL emission.
- Supporting state holders:
  - ``django/db/models/sql/query.py``
    - ``query.combinator`` identifies ``union``/``difference``/``intersection`` flow.
    - ``query.distinct_fields`` indicates explicit ``distinct('field', ...)``.
    - ``query.annotation_select`` indicates active annotation projection.
  - ``django/db/models/query.py``
    - ``count()``, ``exists()``, and evaluation through ``_fetch_all/__iter__`` are evaluation entry points expected to flow into the same compile seam.
- Test locus: ``tests/queries/test_qs_combinators.py``
  - Existing requirement traceability comments and dedicated DJANGO12908 tests remain as verification anchors.

Boundary and dependency rules
----------------------------

- Dependency direction is strict:
  - Query construction mutates ``query`` state.
  - Query construction mutates ``query`` state (including ``query.combinator``, ``query.distinct_fields``, ``query.annotation_select``).
  - ``QuerySet`` evaluation methods request compilation through ``Query.get_compiler()`` and/or ``QuerySet`` result-fetch methods, and
    the compiler reads that state to decide legality.
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
- Evaluation entry points for requirement coverage:
  - ``QuerySet.count()``: ``QuerySet.count`` -> ``Query.get_count`` -> compiler execution -> ``as_sql`` seam.
  - ``QuerySet.exists()``: ``QuerySet.exists`` -> ``Query.has_results`` -> compiler execution -> ``as_sql`` seam.
  - ``list(qs)``: ``QuerySet.__iter__`` -> ``_fetch_all`` -> ``_iterable_class``/``_iterator`` -> compiler execution -> ``as_sql`` seam.
  - Repeated calls for all three must re-enter the same seam and re-raise identical ``NotSupportedError`` + message; this is an idempotence-by-design requirement.
- Implementation-local contract artifact:
  - ``DJANGO12908_EXCEPTION_CONTRACT = ("NotSupportedError", "annotate() + union() + distinct(fields) is not supported.")`` used by tests to enforce explicit path checks.

Dependency-direction notes
-------------------------

- No new modules are introduced.
- No changes are made to model/schema/API contracts.
- Backend-specific behavior remains behind existing feature flags.

Open structural placeholders
---------------------------

- Placeholder remains in code comments in ``compiler.py`` marking the guard seam.
- Future implementation phase should keep the rejection guard executable and avoid changing this seam location.

Completion status
----------------

- All seven requirements are mapped to compiler-level ownership, evaluation seams, and verification anchors.
- Repository includes updated architecture artifact and traceability-aligned comments in test/complier ownership path.
- Structural readiness: compiler seam, interfaces, boundaries, and dependency direction are explicitly documented for list/count/exists idempotence.
