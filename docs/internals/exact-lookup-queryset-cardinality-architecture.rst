Exact-lookup queryset cardinality architecture
==============================================

Scope
-----

This contract places ``DJANGO-11797-009`` and ``DJANGO-11797-010`` in the
existing ORM query structure. It preserves the established one-result
boundary, including result windows with an offset, and introduces no new
query representation or lookup path.

Ownership and boundaries
------------------------

``django.db.models.sql.query.Query`` owns queryset result-window state through
``low_mark`` and ``high_mark``. ``Query.set_limits()`` owns construction of
that state, while ``Query.has_limit_one()`` is the query boundary contract
that reports whether the window contains exactly one position. The contract
does not require a zero ``low_mark``.

``django.db.models.lookups.Exact.process_rhs()`` owns the exact-lookup RHS
cardinality policy. For a ``Query`` RHS, it consumes
``Query.has_limit_one()`` and either admits the query to the established RHS
processing path or raises the established cardinality error. It does not
calculate or rewrite slice bounds.

The inherited lookup processing and SQL compiler remain downstream consumers
of an admitted query. They do not own exact-lookup cardinality validation.

Dependency direction
--------------------

The dependency remains ``Exact`` lookup -> ``Query`` result-window contract
-> inherited RHS processing -> SQL compiler. ``Query`` does not depend on
lookup classes, and neither inherited processing nor the compiler receives a
second cardinality policy.

Integration seam
----------------

The implementation seam is the existing ``Query`` branch in
``Exact.process_rhs()``. That branch must use ``Query.has_limit_one()`` as its
only cardinality decision:

* a one-position window is admitted without changing ``low_mark`` or
  ``high_mark``;
* every other window is rejected before inherited RHS processing;
* after admission, the existing select-field normalization and inherited
  processing continue to own their current responsibilities.

No new adapter, public API, model, schema, compiler, or database-backend seam
is required.

Requirement placement
---------------------

* ``DJANGO-11797-009``: ``Query.set_limits()`` owns both zero-offset and
  nonzero-offset one-position windows; ``Query.has_limit_one()`` identifies
  them; ``Exact.process_rhs()`` admits them without taking ownership of their
  bounds.
* ``DJANGO-11797-010``: ``Exact.process_rhs()`` owns rejection of a ``Query``
  for which ``Query.has_limit_one()`` is false and preserves the established
  error contract.

Implementation readiness
------------------------

The later implementation locus is confined to the existing ``Query`` branch
of ``Exact.process_rhs()``. Verification belongs in
``tests.lookup.tests.ExactLookupQuerysetCardinalityContractTests`` and covers
one-result windows with and without offsets plus windows that are not limited
to one result. The ``Query`` limit representation, lookup inheritance chain,
and SQL compilation structure require no architectural change.
