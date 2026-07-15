# DJ11179-007 — Narrow regression assertion for no-dependency fast-delete and stale key invalidation

## Requirement
- **GUID:** `DJ11179-007`
- **Scope:** single no-dependency instance delete flow should confirm in-memory PK reset (`instance.pk is None`) and in-process stale-key invalidation (`objects.filter(pk=old_pk).exists() is False`) after a successful `instance.delete()` call.

## Requirement-to-Architecture Map
- `DJ11179-007` → `tests/delete_regress/tests.py:DeletePkResetNoDependencyTests.test_fast_delete_instance_set_pk_none`
  - Pressure: keep the regression test narrowly focused on a dependency-free instance and assert both in-memory and stale-key invariants in one path.
- `DJ11179-007` → `django/db/models/base.py:Model.delete()`
  - Pressure: preserve this as the public invocation boundary; no direct PK policy is owned here.
- `DJ11179-007` → `django/db/models/deletion.py:Collector.delete()`
  - Pressure: own the no-dependency fast-delete success boundary that currently clears PK via metadata.
- `DJ11179-007` → `tests/delete_regress/tests.py` stale-liveness check
  - Pressure: confirm deletion side-effects through manager-query contract (`filter(pk=old_pk).exists()` is false) in same process.

## Placement and Ownership
- **Primary owner for behavior:** `Collector.delete()` in `django/db/models/deletion.py` (fast-delete branch plus post-delete settlement boundaries).
- **API boundary owner:** `Model.delete()` in `django/db/models/base.py` (entry point and orchestration handoff).
- **Verification owner:** `DeletePkResetNoDependencyTests` in `tests/delete_regress/tests.py` (acceptance artifact and regression guard).

## Boundaries and Contracts
- **Boundary A — Invocation boundary (`Model.delete()`):**
  - Input: explicit `delete()` call on a persisted instance.
  - Contract: delegate to collector orchestration without introducing branch-specific PK mutation logic.
- **Boundary B — No-dependency fast-delete boundary (`Collector.delete()`):**
  - Input: single-model single-instance candidate satisfying `self.can_fast_delete(instance)`.
  - Contract: successful SQL delete then PK transition to `None` via `model._meta.pk.attname`.
  - Failure contract: on exception, preserve current in-memory state and propagate the failure.
- **Boundary C — Invariant assertion boundary (verification seam):**
  - Input: captured `old_pk` from pre-delete state and post-delete test subject.
  - Contract: stale PK must be unreachable from manager APIs after return (`filter(pk=old_pk).exists()` is false).
- **Boundary D — Scope-sealing seam:**
  - Ensure only dependency-free flows are covered by this assertion set; dependency-managed or bulk delete semantics remain under existing fast-path/cascade contracts.

## Dependency Direction
- `Model.delete()` depends on `Collector` for deletion execution and receives completion signal only.
- `Collector.delete()` depends on transaction + SQL primitives and model metadata (`_meta.pk.attname`) for PK-agnostic identity transitions.
- Regression test depends on no new runtime modules beyond tested model class and manager API.
- No new dependency is introduced from fast-delete behavior into dependency-management/bulk-delete code paths.

## Integration-Seam Skeletons
- **Seam 1 (collector-only regression lane):** keep `DJ11179-007` test coverage linked to `Collector.delete()` fast-path success path without widening scope to related-object flow checks.
- **Seam 2 (single-sequence assertion lane):** in `test_fast_delete_instance_set_pk_none`, keep the sequence `create -> capture old_pk -> delete -> assert None pk -> assert no stale key`.
- **Seam 3 (non-target-path firewall):** maintain current suite-level separation that dependency/bulk delete tests stay separate and are unaffected.

## Completion Status
- Structural placement is explicit for test and runtime loci under `DJ11179-007`.
- Ownership boundaries are bounded and dependency direction is constrained to API->Collector->DB contracts plus verification via manager lookup.
- Requirement-to-architecture traceability is present in this file and in existing test mapping constants.
