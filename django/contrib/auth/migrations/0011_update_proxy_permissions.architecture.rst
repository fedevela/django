G70-001, G70-002, G70-003, and G70-004 Architecture: auth.0011_update_proxy_permissions
======================================================

Requirement-to-architecture map
-------------------------------

- G70-001 -> ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``
  - loop ownership: ``update_proxy_model_permissions`` drives tuple-level migration policy for proxy models
  - verification seam: ``tests/auth_tests/test_auth_proxy_permissions_migration_g70_001.py``
- G70-002 -> ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``
  - pressure O1: missing required tuple should be materialized once per key during forward execution.
  - pressure O2: batch processing is tuple-local; each missing key increases rowcount by one, no cross-tuple coupling.
  - pressure O3: uniqueness on ``(content_type_id, codename)`` must be respected as a precondition boundary.
  - verification seam: ``tests/auth_tests/test_auth_proxy_permissions_migration_g70_001.py``
- G70-003 -> ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``
  - pressure O1: rerun of forward migration on already-migrated DB must preserve rowcount for every existing ``(content_type_id, codename)`` tuple.
  - pressure O2: rerun must not add duplicate permission rows for already-present tuples.
  - pressure O3: rerun must terminate without unique-constraint failure and keep required tuples present.
  - verification seam: ``tests/auth_tests/test_auth_proxy_permissions_migration_g70_001.py``
- G70-004 -> ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``
  - pressure R1: migrated DB from Django 2.0.13/2.1.8 with recreated proxy history must complete forward migration without unique-index cleanup.
  - pressure R2: pre-existing legacy ``auth_permission`` rows from those upgrade paths must not cause migration failure.
  - pressure R3: migration success must hold for same-app-label and different-app-label recreated-proxy transitions.
  - verification seam: ``tests/auth_tests/test_auth_proxy_permissions_migration_g70_004.py`` and ``django/contrib/auth/migrations/0011_update_proxy_permissions.py``

File and module placement decisions
----------------------------------

- Keep all tuple policy in the migration module as the sole ownership boundary for data transition concerns.
- Keep tuple-level behavior in ``update_proxy_model_permissions`` scope, not models, schema editors, or service layers.
- Keep test mapping and scenario coverage in ``tests/auth_tests`` as the verification boundary.
- Keep rerun-idempotency as a forward-loop execution policy; no new control-plane module is introduced.
- Keep recreated-proxy resilience handling inside the existing per-tuple loop, with no new abstraction layer.

Ownership and boundaries
------------------------

- Ownership unit: ``update_proxy_model_permissions`` (forward + reverse paths via ``reverse`` flag).
- Migration boundary: this artifact remains a migration-time adapter over historical models from ``apps.get_model``.
- App boundary: permission writes/read only through historical model handles from ``apps.get_model``.
- Data boundary: ``Permission`` rows keyed by ``(content_type_id, codename)`` are the guarded state.
- Idempotency boundary for ``G70-003``: existing tuples for target keys are immutable during rerun.
- Legacy-upgrade boundary for ``G70-004``: existing target tuples represent completion and must be treated as terminal NOOP state.

Interface and contract artifacts
-------------------------------

- Contract C1 (tuple discovery):
  - Input: ``Model._meta`` for each proxy model in migration registry.
  - Output: required tuple set ``[(content_type_id, codename)]`` from ``default_permissions`` and ``opts.permissions``.
- Contract C2 (target existence precondition):
  - If ``Permission`` already exists for target key, skip tuple mutation branch.
- Contract C3 (mixed state):
  - Preserve pre-existing tuples and execute migration transitions only for missing tuples.
- Contract C4 (error handling):
  - ``IntegrityError`` during update/create is treated as local "already satisfied" state for that tuple.
- Contract C5 (forward-only insertion behavior):
  - In forward execution, ``Permission.objects.filter(new_content_type, codename).exists()`` gates mutation.
  - If source retarget does not update any row, insert one tuple for that key.
- Contract C6 (batch locality):
  - Required permissions are iterated in ``required_permissions`` set; each key is handled independently.
- Contract C7 (unique-index tolerance):
  - If update/create path raises ``IntegrityError`` at target key, boundary treats it as no-op completion for that key.
- Contract C8 (rerun rowcount invariance):
  - If tuple exists at start of iteration, the rerun branch must emit no write for that key.
- Contract C9 (rerun convergence):
  - After successful first forward pass, second forward run keeps required tuples present and stable with no additional key cardinality.
- Contract C10 (legacy presence short-circuit):
  - If the target key already exists before mutations, the loop marks the key as done and returns NOOP.
- Contract C11 (legacy collision tolerance):
  - Any ``IntegrityError`` in update/create paths means the required key is already satisfied and migration continues.
- Contract C12 (upgrade-route parity):
  - The same tuple policy applies regardless of whether recreated-proxy transitions share or change app labels.

Dependency-direction notes
-------------------------

- Upward dependency (migration runtime order):
  - ``('auth', '0010_alter_group_name_max_length')``
  - ``('contenttypes', '0002_remove_content_type_name')``
- Inward dependency from data migration layer:
  - ``auth`` and ``contenttypes`` historical models via ``apps.get_model`` only.
- G70-003 dependency direction:
  - writes are attempted only after the current tuple state is read and classified.
  - duplicate-key or pre-existing-key branches must not alter rowcount state, only transition control locally.
- G70-004 dependency direction:
  - no new imports, services, or cross-app call sites; legacy-row outcomes are consumed locally by the tuple gate and collision handler.
- No new cross-app imports beyond existing historical model access.

Integration-seam skeletons
---------------------------

- Seam S1: ``Permission`` queryset existence gate keyed by ``(content_type_id, codename)``.
- Seam S2: ``ContentType`` resolution for concrete/proxy tuple endpoints.
- Seam S3: reverse execution path via ``revert_proxy_model_permissions`` swapping source/target.
- Seam S4: retarget branch from source tuple to target content type.
- Seam S5: creation branch for concrete key-missing case.
- Seam S6: rerun guard for already-present keys (``DONE_NOOP``).
- Seam S7: integrity collision sink mapped to tuple-local completion (``DONE_ALREADY_PRESENT``).
- Seam S8: legacy target presence branch for recreated-proxy rows.
- Seam S9: non-disruptive collision recovery for mixed historical states in ``G70-004``.

Seam-to-contract mapping
------------------------

- S1 -> C2, C8
- S4 -> C3, C5
- S5 -> C5, C6
- S6 -> C8, C9
- S7 -> C4, C7
- S8 -> C10, C12
- S9 -> C11, C12
- C9 is satisfied when S1 returns pre-existing for all required tuples or S5/S4 ensure one-time materialization.

Traceability and completeness check
----------------------------------

- ``G70-001`` obligation 1 (existing tuple rowcount preserved) -> ``C2``, ``C3``, S1
- ``G70-001`` obligation 2 (existing tuple detected, no integrity error) -> ``C4``
- ``G70-001`` obligation 3 (mixed present/missing handling) -> ``C3``, C4
- ``G70-002`` obligation 1 (missing tuple materializes once) -> ``C5``, ``C6``, S5
- ``G70-002`` obligation 2 (batch tuple-local insertion) -> ``C6``, S4, S5
- ``G70-002`` obligation 3 (unique index safe path) -> ``C7``, C4
- ``G70-003`` obligation 1 (rerun rowcount invariant) -> ``C2``, ``C8``, S1
- ``G70-003`` obligation 2 (no duplicate row growth) -> C8, S6, C7, S7
- ``G70-003`` obligation 3 (rerun no constraint error, required tuples present) -> C9, C4, S5, S7
- ``G70-004`` obligation 1 (legacy 2.0.13/2.1.8 upgrade completes without manual cleanup) -> C10, C11, S1, S7
- ``G70-004`` obligation 2 (preexisting proxy rows are accepted) -> C10, S8
- ``G70-004`` obligation 3 (same-app-label and different-app-label scenarios remain valid) -> C12, S8, S9

Completion status
----------------

- Structural-ready status: **Ready for implementation** with explicit ``G70-004`` ownership, contracts, seam mappings, and requirement traceability.
