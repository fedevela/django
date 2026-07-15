DJ12747-12747
========================

Zero-match :meth:`QuerySet.delete()` return-shape normalization

This artifact places deterministic logic from requirements :red:`GUID: DJ12747-001`,
:red:`GUID: DJ12747-002`, and :red:`GUID: DJ12747-003` into stable structural
ownership and integration seams.

Requirement-to-architecture mapping
----------------------------------

- DJ12747-001 (zero-match tuple contract)  
  - Ownership: ``django/db/models/query.py:QuerySet.delete``  
  - Structural pressure: public API boundary and return-shape contract at
    method return.

- DJ12747-002 (policy-equivalence FK vs non-FK paths)  
  - Ownership: ``django/db/models/deletion.py:Collector.delete``  
  - Structural pressure: shared emission seam between fast-delete and data-delete
    paths.

- DJ12747-003 (non-empty zero-deletion counters are model labels with zero values)  
  - Ownership: ``django/db/models/deletion.py:Collector.delete`` return shaping
    before handoff to ``QuerySet.delete``.  
  - Structural pressure: counter-map key/value invariants.

Placement and boundary decisions
-------------------------------

- Keep request orchestration in ``QuerySet.delete`` only.  
  Responsibilities:
  1. Validate deletion preconditions.
  2. Build and run a ``Collector`` on the same write DB.
  3. Propagate ``(deleted_count, deleted_counters)``.
  4. Clear queryset cache.

- Keep model traversal, collector buckets, and SQL execution in ``Collector``.  
  Responsibilities:
  1. Accumulate counters by model label.
  2. Emit the final counter dictionary for all zero and non-zero flows.
  3. Preserve FK-capable and non-FK collection behavior internals.

- Keep policy-specific assertions and regression tests in:
  ``tests/delete/tests.py`` methods
  ``test_dj12747_001_queryset_delete_zero_rows_returns_zero_count_and_dict_shape``,
  ``test_dj12747_002_zero_rows_query_set_delete_unifies_key_presence_policy_fk_vs_non_fk``,
  ``test_dj12747_003_zero_delete_nonempty_dict_uses_meta_label_keys_and_zero_values``.

Dependency direction
-------------------

``QuerySet.delete`` -> ``Collector.collect`` -> ``Collector.delete`` -> DB/query layer.

- Dependency direction is strictly downward (public API to internal collector to DB)
  with no reverse dependency into API callers.
- Zero-row normalization must occur before values leave the collector seam so all
  callers observe the same contract.

Integration seam
---------------

- Primary seam: end of ``Collector.delete`` return path
  (``django/db/models/deletion.py`` around final ``return``).
  - This is the singular location to normalize zero-row counter-shape policy.

- Secondary seam: post-collector handoff in ``QuerySet.delete``
  (``django/db/models/query.py`` after ``collector.delete()``).
  - Contract consumer only; no transformation logic belongs here in this phase.

Contract skeleton for implementation
-----------------------------------

The zero-match contract can be represented as:

- ``(deleted_count, counters)``
- ``deleted_count == 0`` when no rows match.
- ``counters`` is always a ``dict[str, int]``.
- For zero-match with non-empty counters:
  - every key is ``model._meta.label`` of an involved model,
  - every value is ``0``.
- FK-capable and non-FK codepaths must produce structurally equivalent key
  presence.

Readiness check for implementation
---------------------------------

- Requirements mapped to concrete files and seams: complete.
- Ownership boundaries defined (public API vs collector internals): complete.
- Dependency direction expressed and one normalization seam identified: complete.
- Structural traceability preserved with requirement IDs and touched loci.

