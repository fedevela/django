Grouped aggregate exact-lookup regression architecture
======================================================

Scope
-----

This verification contract places ``DJANGO-11797-011`` and
``DJANGO-11797-012`` in the existing lookup test structure. It verifies the
SQL boundary established by the grouped-aggregate exact-lookup change and
uses the existing Django test runner as the compatibility boundary. It adds
no production API, query representation, model, or backend-specific path.

Architecture pressures
----------------------

``DJANGO-11797-011`` requires one owner for constructing the reported query,
one compilation boundary that exposes the embedded subquery SQL, and paired
positive and negative checks of its projection and grouping. The checks must
distinguish the aggregate annotation and email grouping from the historical
primary-key fallback without depending on database identifier quoting.

``DJANGO-11797-012`` requires the new regression case to remain inside the
established ``lookup`` test application so it runs with the relevant lookup
tests. Compatibility is a suite outcome owned by the Django test runner, not
a second runtime policy or a production-code responsibility.

Ownership and boundaries
------------------------

``tests.lookup.tests.GroupedAggregateExactLookupTraceabilityTests`` is the
verification owner. Its implementation-stage successor owns construction of
the filtered, grouped, annotated, projected, and one-row-sliced queryset and
embedding that queryset as the right-hand side of an exact lookup.

The outer queryset's ``Query`` object is the test-facing compilation
boundary. The test compiles it through the normal backend compiler and
observes SQL only; it does not duplicate lookup processing or compiler
behavior. Clause inspection belongs to test-local helpers if extraction is
needed, and those helpers must accept backend quoting rather than normalize
production SQL generation.

The production ownership boundary remains unchanged:

* ``Query`` owns projection, annotation, grouping, filtering, and slicing;
* ``Exact.process_rhs()`` owns admission and projection-fallback handling for
  the exact-lookup right-hand side;
* the SQL compiler owns rendering the resulting query state.

Verification contracts
----------------------

The regression fixture contract produces one outer queryset whose embedded
right-hand side was built in this order: filter null email values, group by
email, annotate ``Max('id')``, project the annotation, and slice to one row.
Both ``DJANGO-11797-011`` assertions consume SQL from that same structural
shape so the positive and exclusion obligations cannot drift apart.

The SQL-shape contract has two independently reportable sides:

* the embedded subquery selects the aggregate expression and its ``GROUP BY``
  clause names email;
* the embedded subquery does not substitute the model primary key in either
  the selected expression or the grouping clause.

Assertions are scoped to the embedded subquery clauses. Outer-query primary
key selection is valid and must not be mistaken for the rejected inner
fallback shape. Identifier comparisons must use compiler- or
connection-aware quoting, or otherwise isolate identifiers without assuming
one database's quote characters.

Dependency direction
--------------------

The verification dependency is ``lookup regression test`` -> ``public
QuerySet construction`` -> ``Exact`` lookup seam -> ``Query`` state -> SQL
compiler. Test-only clause inspection depends on the generated SQL boundary;
production code does not depend on test helpers or verification artifacts.

The compatibility dependency is ``Django test runner`` -> ``lookup`` test
application -> new regression case plus existing lookup cases. No test method
may simulate suite passage with an unconditional assertion; passage is
established only by the runner's aggregate result.

Integration seams and placement
-------------------------------

The defect-specific integration seam stays in ``tests/lookup/tests.py``
beside the existing grouped-aggregate and exact-lookup contract tests. The
three Hod loci in
``GroupedAggregateExactLookupTraceabilityTests`` provide implementation-stage
placement as follows:

* ``DJANGO-11797-011`` positive SQL-shape flow belongs in the aggregate/email
  regression method;
* ``DJANGO-11797-011`` primary-key exclusion belongs in the paired negative
  regression method, sharing query construction and clause boundaries with
  the positive case;
* ``DJANGO-11797-012`` compatibility flow maps to focused runner selection of
  the new case and existing relevant lookup classes. Its traceability
  placeholder is not itself evidence of compatibility and should not remain
  as a passing test after implementation.

No new test application, model, database feature flag, adapter, port, or
production module is required. Test-local helpers are justified only when
they keep query construction or embedded-clause isolation shared between the
paired ``DJANGO-11797-011`` checks.

Requirement placement
---------------------

* ``DJANGO-11797-011``: owned by the grouped-aggregate exact-lookup regression
  class in ``tests/lookup/tests.py``; observed at the compiled outer-query SQL
  boundary; expressed as paired positive aggregate/email and negative
  primary-key checks against embedded-subquery clauses.
* ``DJANGO-11797-012``: owned by the existing ``lookup`` test application and
  Django test runner; established by running the defect-specific regression
  together with the relevant existing exact-lookup tests and propagating all
  failures and errors.

Implementation readiness
------------------------

Every obligation has an existing repository home. Later implementation is
confined to replacing the three traceability placeholders in
``GroupedAggregateExactLookupTraceabilityTests`` with shared query/SQL
scaffolding and real ``DJANGO-11797-011`` assertions, then using the focused
``lookup`` runner result for ``DJANGO-11797-012``. Production behavior,
schemas, public contracts, and backend compilers require no further
structural change for this verification issue.
