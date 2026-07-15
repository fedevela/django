# DJ11179-004 — Preserve in-memory PK across failed no-dependency delete attempts

## Requirement
- **GUID:** `DJ11179-004`
- **Scope:** no-dependency fast-delete rollback and exception paths in `Collector.delete()` must not mutate in-memory identity until deletion succeeds.

## Requirement-to-Architecture Map
- `DJ11179-004` → `django/db/models/deletion.py:Collector.delete()`, fast-delete guard block (`len(self.data) == 1 and len(instances) == 1` with `self.can_fast_delete(instance)`).
  - Pressure: localize the rollback-safety contract at the exact mutation boundary where PK reset currently occurs.
- `DJ11179-004` → `django/db/models/deletion.py` transaction path using `transaction.mark_for_rollback_on_error()`.
  - Pressure: ensure failure semantics from delete/savepoint are structurally separated from success-only identity transitions.
- `DJ11179-004` → `tests/delete_regress/tests.py:DeletePkResetNoDependencyRollbackTraceabilityTests`
  - Pressure: keep acceptance points anchored to failure, savepoint-failure, and retry-success scenarios.

## Placement and Ownership
- **Primary owner:** `Collector` (implementation locus in `django/db/models/deletion.py`)
- **Boundary owner:** `Collector.delete()` branch-local state transition boundary for no-dependency fast path.
- **Caller/API boundary:** `Model.delete()` remains the external request boundary and does not own in-memory PK mutation policy.

## Boundary Decisions
- **Fast-delete success boundary:** `Collector.delete()` branch for single-instance no-dependency deletion.
  - Only this boundary may apply `setattr(instance, model._meta.pk.attname, None)`.
  - Attribute write is only allowed after successful return from `sql.DeleteQuery(...).delete_batch(...)`.
- **Failure boundary (rollback-safe):** if `delete_batch` raises (including savepoint-level exceptions), the boundary must not execute PK mutation.
- **Retry boundary:** because failure path preserves PK, the retry path remains structurally identical and can then take the same success transition.

## Structural Contracts
- **Rollback-Safety Contract**
  - Input: `instance` selected by fast-delete branch with original PK captured externally by caller object lifetime.
  - Rule: exceptions from the database delete must leave `instance.pk` unchanged.
  - Required outcome: caller observes same in-memory identity as before invocation.
- **Success Transition Contract**
  - Input: no-dependency delete block completes without exception.
  - Rule: set PK to `None` via metadata attname in same branch before returning collector tuple.
- **Traceability Contract**
  - Mapping stays requirement-local and test-local through
    `DeletePkResetNoDependencyRollbackTraceabilityTests`.

## Dependency Direction
- `Collector` depends on:
  - `transaction.mark_for_rollback_on_error` for exception-safe execution semantics.
  - `sql.DeleteQuery` for actual row removal.
  - `model._meta.pk.attname` for PK-type-agnostic identity mutation.
- No new coupling to signal, manager, or traversal modules for this requirement.

## Integration Seams
- **Seam A — No-dependency fast-delete execution**
  - Located in `Collector.delete()` guard branch.
  - Houses transactional execution and provides failure signal to identity state transition.
- **Seam B — Post-delete identity handoff**
  - Same guard branch after successful delete return.
  - Performs only the PK-reset transition; boundary intentionally excludes exception catch/fail flows.
- **Seam C — Retry continuation**
  - Later successful invocation reuses the same success boundary because unchanged PK remains valid.

## Readiness Confirmation
- All traced `DJ11179-004` obligations are mapped to explicit module/boundary locations.
- At least one architecture artifact is created and requirement-traceable.
- Structural ownership and dependency direction are explicit for implementation.
