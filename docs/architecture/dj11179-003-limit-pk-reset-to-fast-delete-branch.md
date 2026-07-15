# DJ11179-003 — Limit PK reset to dependency-free fast-delete branch

## Requirement
- **GUID:** `DJ11179-003`
- **Scope:** Apply in-memory PK reset only in the no-dependency fast-delete branch of `Collector.delete()` in `django/db/models/deletion.py`, and keep dependency-managed collector settlement flows structurally unchanged.

## Requirement-to-Architecture Map
- `DJ11179-003` → `django/db/models/deletion.py:Collector.delete()` fast-delete decision point (`len(self.data) == 1 and len(instances) == 1`, `self.can_fast_delete(instance)`).
  - Pressure: branch ownership and boundary of the PK-reset mutation.
- `DJ11179-003` → `django/db/models/deletion.py:Collector.delete()` collector settlement section (`for model, instances in self.data.items(): setattr(instance, model._meta.pk.attname, None)`).
  - Pressure: preserve dependency-managed path without fast-delete-only mutation.
- `DJ11179-003` → `tests/delete_regress/tests.py:DeletePkResetFastDeleteBranchTraceabilityTests`
  - Pressure: keep verification traceability anchored to branch semantics.

## Ownership and Topology Decisions
- **Primary owner:** `Collector` in `django/db/models/deletion.py` for branch selection and in-memory instance state transitions.
- **Boundary owner:** `Collector.delete()` is the transition boundary between three regions:
  - fast-delete branch (single model + single instance + `can_fast_delete`)
  - dependency-managed fast delete collection path (`self.fast_deletes` + related operations)
  - collector settlement path over `self.data`
- **Cross-module boundary:** `Model.delete()` continues to invoke `Collector` without owning PK-reset behavior.

## Structural Contracts
- **Path-Gated PK Reset Contract**
  - Precondition: dependency-free fast-delete branch is selected (`self.can_fast_delete(instance)` true in the single-instance branch).
  - Action: set `instance` PK to `None` through `model._meta.pk.attname` in that branch immediately after successful `delete_batch` and before returning.
  - Exclusion: this mutation is not applied in collector-settlement mutation loops.
- **Dependency-Managed Invariant**
  - `Collector.delete()` settlement loop remains responsible only for its own bounded post-delete updates and must not be treated as a fast-delete mutation site.

## Dependency Direction
- `Collector` depends on model metadata (`_meta.pk.attname`) and transaction/SQL primitives.
- `Collector` must not depend on concrete delete policy implementations to perform PK reset; policy is expressed by the branch decision already in the method.
- Existing dependency-management utilities (`self.dependencies`, `self.data`, `self.fast_deletes`) remain unchanged owners.

## Integration Seams (skeleton-ready)
- **Seam A — Fast-delete transition seam:** inside `Collector.delete()` guard block before early return. This seam now carries the requirement-specific post-delete identity transition.
- **Seam B — Settlement seam:** shared non-branch post-loop mutation area. For this requirement, remains the collector-managed boundary and explicitly excludes fast-delete-only PK-reset semantics.

## Readiness Confirmation
- `DJ11179-003` obligations are mapped to explicit modules and seams.
- PK-reset logic is explicitly architected as a fast-delete-only transition.
- Dependency-managed settlement path is preserved as a separate boundary.
- Traceability remains linked to `tests/delete_regress/tests.py` coverage identifiers.
