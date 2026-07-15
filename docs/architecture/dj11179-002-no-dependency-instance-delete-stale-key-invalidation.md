# DJ11179-002 — No-dependency instance delete must make stale PK unreachable

## Requirement
- **GUID:** `DJ11179-002`
- **Scope:** persisted instance delete flow on no-dependency/fast path must keep database row removed and render captured old PK non-resolvable in the same process after successful return.

## Requirement-to-Architecture Map
- `DJ11179-002` → `django/db/models/base.py:Model.delete()`
  - Pressure: preserve model-level orchestration ownership and handoff to persistence coordinator.
  - Architectural decision: keep `Model.delete()` as entry boundary and requirement boundary for invocation semantics.
- `DJ11179-002` → `django/db/models/deletion.py:Collector.delete()` fast-delete branch (`len(self.data) == 1 and len(instances) == 1` and `self.can_fast_delete(instance)`).
  - Pressure: fast path is the primary behavioral contract boundary for no-dependency deletes.
  - Architectural decision: this branch is responsible for both DB deletion evidence and in-memory stale-key invalidation obligations.
- `DJ11179-002` → `django/db/models/deletion.py:Collector.delete()` post-loop mutation section.
  - Pressure: guarantees stale references are invalid from DB after collector-owned deletes on non-fast path.
  - Architectural decision: non-fast path remains the canonical fallback branch for same contract.
- `DJ11179-002` → `tests/delete_regress/tests.py`
  - Pressure: acceptance coverage bound to stale PK lookup behavior across `filter(...).exists()` and `get(...)`.
  - Architectural decision: keep test contract at the same seam as delete behavior.

## Placement and Ownership
- **Owner:** `Collector` in `django/db/models/deletion.py` for persistence + stale-key post-state guarantees.
- **API boundary:** `Model.delete()` in `django/db/models/base.py` retains public orchestration role.
- **Consumer boundary:** model managers/query APIs (`objects.filter/get`) in calling code hold DB lookup responsibility and are expected to reflect deletion by absence of rows.

## Boundary and Contracts
- **Boundary A (invocation):** `Model.delete()` delegates work into `Collector` and does not perform direct row-deletion logic itself.
- **Boundary B (no-dependency fast delete):** `Collector.delete()` owns deletion decision and success sequencing.
  - Input contract: single model/single instance + `can_fast_delete(instance)`.
  - Success contract: delete old row from DB before exposing post-delete in-memory state transition.
  - Failure contract: propagate exception without mutating captured PK.
- **Boundary C (state settlement):** `Collector.delete()` clears identity fields post-delete through metadata-driven path (`setattr(instance, model._meta.pk.attname, None)`) to keep stale in-memory references from being associated with a live row.
- **Boundary D (lookup invariants):** callers using `old_pk` must receive DB absence (`filter(...).exists() == False`, `get(...).DoesNotExist`) after successful delete.

## Dependency Direction
- `Model.delete()` depends on `Collector` orchestration API.
- `Collector.delete()` depends on DB SQL delete primitive (`sql.DeleteQuery.delete_batch`) and model metadata (`model._meta.pk.attname`) for PK-agnostic settlement.
- `Collector` does **not** depend on concrete field subclasses for stale-key policy.

## Dependency-managed Path Constraint
- No change to non-no-dependency/cascading semantics; existing dependency and traversal owners remain unchanged.

## Integration-Seam Skeletons (architecture-only)
- **Seam 1:** fast-path success checkpoint inside `Collector.delete()` before and after SQL batch removal.
  - Inputs: captured old PK + model/instance identity.
  - Output: hard requirement that old PK becomes unreachable through manager lookup.
- **Seam 2:** state-settlement pass over `self.data` after all SQL deletion branches.
  - Inputs: all collected instances.
  - Output: metadata-driven PK nulling contract.

## Readiness Confirmation
- Structural owner/boundary map is established for the no-dependency stale-key invariant.
- All obligations from `DJ11179-002` are mapped to repository loci.
