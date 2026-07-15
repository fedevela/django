# DJ11179-001 — No-dependency instance delete should clear in-memory PK

## Requirement
- **GUID:** `DJ11179-001`
- **Scope:** instance-level `Model.delete()` path using Collector fast-delete branch (`len(self.data) == 1 and len(instances) == 1` and `can_fast_delete(instance)`).

## Requirement-to-Architecture Map
- `DJ11179-001` → `Collector.delete()` fast-delete decision branch:
  - Location: `django/db/models/deletion.py`, method `Collector.delete()`, fast-path block with `self.can_fast_delete(instance)`.
  - Pressure: define an ownership boundary where the deletion coordinator is responsible for post-commit in-memory state transitions.
- `DJ11179-001` → in-memory state reset contract:
  - Location: `django/db/models/deletion.py`, post-collection mutation area and fast-delete branch.
  - Pressure: PK reset must be centralized behind the same attribute-addressing contract (`model._meta.pk.attname`) to support non-default PK types.
- `DJ11179-001` → verification locus:
  - Location: `tests/delete_regress/tests.py`.
  - Pressure: keep test intent bound to the same architectural boundary (instance-level delete, no dependency fast path).

## Placement and Ownership
- **Owner:** `Collector` in `django/db/models/deletion.py`
- **Responsibility:** orchestrates delete planning and owns transition of collected instance objects from persisted-state to in-memory-identity-cleared state.
- **Out-of-scope owner for this requirement:** queryset bulk delete semantics, related-object traversal logic, on_delete policy rules, signal dispatch internals.

## Boundaries
- `Collector.delete()` is the integration boundary where:
  - preconditions are checked (`len(self.data)`, `instances` cardinality, `can_fast_delete(instance)`),
  - database mutation is triggered,
  - and in-memory mutation is applied to collected model objects.
- The boundary must keep DB operation contracts (`sql.DeleteQuery.delete_batch`) separated from in-memory contracts (`setattr(instance, model._meta.pk.attname, None)`).

## Contracts (architecture-level)
- **PK Reset Contract**
  - Input: persisted model instance that has just completed successful deletion through no-dependency fast path.
  - Operation: set PK field value via model metadata attname (`instance.<pk_attname> = None` semantics through `setattr`).
  - PK coverage: no type assumptions; must be metadata-driven.
- **Path-Selection Contract**
  - Fast path only when single-model/single-instance with satisfiable `can_fast_delete(...)`.
  - Failure path does not perform this path-level post-delete state contract.
- **Return-State Contract**
  - After `instance.delete()` returns successfully, caller-visible `instance.pk` must reflect `None`.

## Dependency Direction
- `Collector` depends on:
  - `Model._meta.pk.attname` to stay metadata-correct for all PK field types.
  - `transaction.mark_for_rollback_on_error` and `sql.DeleteQuery` for DB-side execution.
- `Collector` must not depend on concrete PK field class names (`AutoField`, `UUIDField`, etc.); it depends on metadata abstraction only.

## Integration Seams (skeleton-ready)
- **Seam 1:** Fast-delete branch post-success transition hook
  - Suggested logical hook: a collector-local transition function (e.g., `_clear_instance_pk(instance, model)`), implemented via `model._meta.pk.attname`.
  - Purpose: centralize in-memory state ownership and make test expectation enforceable.
- **Seam 2:** Fast-delete success/failure boundary
  - Success path applies in-memory state contract.
  - Exception path keeps prior state untouched except for database transaction side effects.

## Implementation Readiness
- No structural changes beyond metadata-driven contract introduction are needed to pass acceptance criteria.
- The implementation locus is ready: `django/db/models/deletion.py` (Collector fast-delete branch and post-delete update section).
