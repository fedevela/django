G70-001 Architecture: auth.0011_update_proxy_permissions
=====================================================

Requirement-to-architecture map
-------------------------------

- G70-001 -> ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``
  - loop ownership: ``update_proxy_model_permissions`` drives tuple-level migration policy for proxy models
  - verification seam: ``tests/auth_tests/test_auth_proxy_permissions_migration_g70_001.py``

File and module placement decisions
----------------------------------

- Keep logic in the migration module as the sole ownership boundary for schema/data transition concerns.
- Keep tuple-level behavior in function scope, not models or model methods.
- Keep test mapping in ``tests/auth_tests`` as verification artifact; no production behavior change there.

Ownership and boundaries
------------------------

- Ownership unit: ``update_proxy_model_permissions`` (forward + reverse paths via ``reverse`` flag).
- Migration boundary: this file must not introduce service-layer abstractions; it remains a migration-time adapter over historical model state.
- App boundary: writes only through historical app registry models from ``apps.get_model``.
- Data boundary: ``Permission`` rows under keys ``(content_type_id, codename)`` are the protected state.

Interface and contract artifacts
-------------------------------

- Contract C1 (tuple discovery):
  - Input: ``Model._meta`` for each proxy model in migration registry.
  - Output: required tuple set ``[(content_type_id, codename)]`` for defaults + ``opts.permissions``.
- Contract C2 (forward direction):
  - Condition: if tuple exists at target ``content_type_id`` prior to mutation, skip that tuple.
  - Effect: keep rowcount unchanged and continue.
- Contract C3 (mixed state):
  - Effect: preserve pre-existing tuples and only transition/insert paths for missing tuples.
- Contract C4 (error handling):
  - DB integrity collision during mutation is interpreted as tuple-already-present condition.

Dependency-direction notes
-------------------------

- Upward dependency (migration runtime order):
  - ``('auth', '0010_alter_group_name_max_length')``
  - ``('contenttypes', '0002_remove_content_type_name')``
- Inward dependency from data migration layer:
  - ``auth`` and ``contenttypes`` model views via ``apps.get_model`` only.
- No new cross-app imports.

Integration-seam skeletons
--------------------------

- Seam S1: ``Permission`` queryset filter/update target keyed by existing ``permissions_query`` and ``content_type``.
- Seam S2: ``ContentType`` lookup for concrete and proxy content types per proxy model.
- Seam S3: reverse execution path routed through ``revert_proxy_model_permissions`` with swapped source/target types.
- Seams are currently represented by existing migration hooks and can be converted to concrete tuple-branch logic during implementation phase.

Traceability and completeness check
----------------------------------

- ``G70-001`` obligation 1 (existing tuple rowcount preserved) -> ``C1``, ``C2``, S1
- ``G70-001`` obligation 2 (existing tuple detected, no integrity error) -> ``C4``
- ``G70-001`` obligation 3 (mixed present/missing handling) -> ``C3``, C4

Completion status
----------------

- Structural-ready status: **Ready for implementation**.
- Updated architecture artifacts: one concrete artifact added.
