G70-001 and G70-002 Architecture: auth.0011_update_proxy_permissions
=====================================================

Requirement-to-architecture map
-------------------------------

- G70-001 -> ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``
  - loop ownership: ``update_proxy_model_permissions`` drives tuple-level migration policy for proxy models
  - verification seam: ``tests/auth_tests/test_auth_proxy_permissions_migration_g70_001.py``
- G70-002 -> ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``
  - pressure O1: missing required tuple should be materialized once per key during forward execution.
  - pressure O2: batch of missing keys should be processed tuple-locally, one insertion path per key.
  - pressure O3: uniqueness on ``(content_type_id, codename)`` must be respected as a precondition boundary.
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
- Contract C5 (forward-only insertion guarantee):
  - In forward execution, ``reverse=False`` and ``Permission.objects.filter(new_content_type, codename).exists()`` gates mutation.
  - If source retarget does not update any row, the design requires a direct create path for the single missing key.
- Contract C6 (batch locality):
  - Required permissions are iterated in ``required_permissions`` set; each ``codename`` is handled without coupling to other keys.
- Contract C7 (unique-index tolerance):
  - If insert/update path raises ``IntegrityError`` at a target key, the boundary treats it as idempotent completion for that key.

Dependency-direction notes
-------------------------

- Upward dependency (migration runtime order):
  - ``('auth', '0010_alter_group_name_max_length')``
  - ``('contenttypes', '0002_remove_content_type_name')``
- Inward dependency from data migration layer:
  - ``auth`` and ``contenttypes`` model views via ``apps.get_model`` only.
- No new cross-app imports.

Dependency-direction constraint for G70-002
------------------------------------------

- ``update_proxy_model_permissions`` depends only on deterministic model metadata from ``_meta`` and stable content type lookup.
- The architecture forbids any filesystem/db helper indirection outside this migration module for this concern.
- Uniqueness behavior is consumed from DB constraints of ``auth_permission(content_type_id, codename)`` and not duplicated in code.

Integration-seam skeletons
--------------------------

- Seam S1: ``Permission`` queryset filter/update target keyed by existing ``permissions_query`` and ``content_type``.
- Seam S2: ``ContentType`` lookup for concrete and proxy content types per proxy model.
- Seam S3: reverse execution path routed through ``revert_proxy_model_permissions`` with swapped source/target types.
- Seams are currently represented by existing migration hooks and can be converted to concrete tuple-branch logic during implementation phase.
- Seam S4 (insertion branch): when forward execution finds no update target, a create path is the only allowed completion mechanism for that key.

Integration-seam skeleton (traceable responsibilities)
------------------------------------------------------

- Seams are represented by tuple-local branches in ``update_proxy_model_permissions``:
  - ``exists_check(codename, target_ct)`` -> idempotent skip
  - ``retarget_attempt(codename, old_ct, new_ct)`` -> migrate from concrete/proxy mapping
  - ``create_missing(codename, new_ct)`` -> single-row creation for forward-missing key
  - ``integrity_collision(codename)`` -> no-op completion for the same key

Traceability and completeness check
----------------------------------

- ``G70-001`` obligation 1 (existing tuple rowcount preserved) -> ``C1``, ``C2``, S1
- ``G70-001`` obligation 2 (existing tuple detected, no integrity error) -> ``C4``
- ``G70-001`` obligation 3 (mixed present/missing handling) -> ``C3``, C4
- ``G70-002`` obligation 1 (exactly-once missing-key insertion in forward) -> ``C5``, C6, S4
- ``G70-002`` obligation 2 (batch one-by-one + no coupling) -> ``C6``, S4
- ``G70-002`` obligation 3 (unique index safe path) -> ``C7``, C4

Completion status
----------------

- Structural-ready status: **Ready for implementation** with explicit G70-002 ownership and seam/capability mapping.
- Updated architecture artifacts: one concrete artifact updated.
