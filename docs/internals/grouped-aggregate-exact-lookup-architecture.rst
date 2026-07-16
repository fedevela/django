Grouped aggregate exact-lookup architecture
===========================================

Scope
-----

This contract places ``DJANGO-11797-001`` through ``DJANGO-11797-008`` in the
existing ORM query structure. It introduces no new query representation or
backend-specific path.

Ownership and boundaries
------------------------

``django.db.models.sql.query.Query`` owns the semantic state of a queryset:
its explicit projection, annotation registry and mask, grouping expressions,
filter tree, and slice bounds. ``Query.has_select_fields`` is the boundary
contract that reports whether a caller supplied an explicit projection.

``django.db.models.lookups.Exact.process_rhs()`` owns only the exact-lookup
RHS contract. It validates one-row cardinality and chooses between preserving
an explicit projection and installing the primary-key fallback for an
unprojected query. It must not reconstruct grouping, filtering, annotations,
or limits.

The SQL compiler remains a downstream consumer of the resulting ``Query``.
No compiler or database backend owns this decision.

Dependency direction
--------------------

The dependency remains ``Exact`` lookup -> ``Query`` public query-state
contract -> SQL compiler. ``Query`` does not depend on lookup classes, and the
compiler is not given lookup-specific recovery behavior.

Integration seam
----------------

The implementation seam is the ``Query`` branch in
``Exact.process_rhs()``. After the existing ``has_limit_one()`` validation,
that branch consults ``Query.has_select_fields``:

* an explicit projection crosses the seam unchanged;
* an absent projection permits the existing single-column primary-key
  fallback.

This keeps the fallback available for ordinary unprojected querysets while
preventing it from overwriting a caller-established aggregate projection and
the grouping coupled to that projection.

Requirement placement
---------------------

* ``DJANGO-11797-001``: ``Query.group_by`` remains owned by ``Query`` and is
  not rewritten at the exact-lookup seam.
* ``DJANGO-11797-002``: ``Query.annotation_select_mask`` and
  ``Query.annotation_select`` carry the projected ``Max('id')`` through the
  seam.
* ``DJANGO-11797-003``: ``Exact.process_rhs()`` owns scalar-subquery
  single-column validity; the explicit ``values('m')`` projection satisfies
  the contract.
* ``DJANGO-11797-004``: ``Query.where`` remains owned by ``Query`` and passes
  unchanged to compilation.
* ``DJANGO-11797-005``: ``Query.annotations`` remains owned by ``Query`` and
  passes unchanged to compilation.
* ``DJANGO-11797-006``: ``Query.low_mark`` and ``Query.high_mark`` remain
  owned by ``Query`` after ``has_limit_one()`` validates the bound.
* ``DJANGO-11797-007``: ``Query.set_values()`` owns standalone aggregate
  projection and grouping construction.
* ``DJANGO-11797-008``: ``Query.set_limits()`` owns slice bounds and does not
  take ownership of projection, filtering, aggregation, or grouping.

Implementation readiness
------------------------

The later implementation delta is confined to the existing ``Query`` branch
of ``Exact.process_rhs()``. Verification belongs in
``tests.lookup.tests.GroupedAggregateExactLookupContractTests`` and observes
the standalone, sliced, and embedded SQL forms. No schema, model, public API,
compiler, or backend changes are required.
