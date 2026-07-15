# DJ11179-005 — Preserve dependency-managed and queryset bulk-delete semantics

## Requirement
- **GUID:** `DJ11179-005`
- **Scope:** prevent any new in-memory `pk`-clearing contract in dependency-managed delete flows and queryset bulk delete paths while preserving existing cascade/null/protect outcomes and signal/dependency behavior.

## Requirement-to-Architecture Map
- `DJ11179-005` → `django/db/models/base.py:Model.delete()`
  - Pressure: keep the public instance-delete API as a delegation boundary to `Collector`; no instance PK contract should be introduced at this boundary for dependency-managed cases.
- `DJ11179-005` → `django/db/models/query.py:QuerySet.delete()`
  - Pressure: keep bulk-delete orchestration as collector-driven and untouched in behavior; avoid introducing PK-clearing assumptions for flow-local objects.
- `DJ11179-005` → `django/db/models/deletion.py:Collector.collect()`
  - Pressure: preserve branching between `can_fast_delete()` and related-object traversal (`self.collect()` on relations), so dependency-managed collection semantics remain unchanged.
- `DJ11179-005` → `django/db/models/deletion.py:Collector.delete()`
  - Pressure: preserve dependency-managed settlement (`on_delete` handling, `self.dependencies`, `self.fast_deletes`, related updates), and keep mutation of in-memory PK to only the intended no-dependency fast path.
- `DJ11179-005` → `tests/delete_regress/tests.py`
  - Pressure: keep traceability for dependency-managed + queryset bulk outcomes in no-behavior-change tests.

## Placement and Ownership
- **Primary owner:** `Collector` in `django/db/models/deletion.py`
  - Owns collection strategy, dependency traversal, and delete-settlement behavior.
- **Caller owners:**
  - `Model.delete()` in `django/db/models/base.py` owns public instance-delete entry semantics and delegates to collector.
  - `QuerySet.delete()` in `django/db/models/query.py` owns public queryset bulk-delete entry semantics and delegates to collector.
- **Out-of-scope for this requirement:** implementing PK reset in dependency-managed and bulk flows, modifying SQL primitives, and changing relation rule algorithms (`CASCADE`, `SET_NULL`, `PROTECT`, etc.).

## Boundaries
- **Boundary A — API delegation**
  - `Model.delete()` and `QuerySet.delete()` are call-site boundaries.
  - Contracts at this boundary:
    - invoke collector with required query state/dependencies,
    - do not apply in-memory PK lifecycle guarantees for dependency-managed or queryset-delete flows.
- **Boundary B — Collection branch selection**
  - `Collector.collect()` is the decision boundary:
    - `can_fast_delete()` path for no-dependency fast-path,
    - dependency traversal and collector graph population for managed-delete paths.
  - This boundary must stay stable: branch conditions and relation traversal remain unchanged for requirement compliance.
- **Boundary C — Delete settlement**
  - `Collector.delete()` is the execution boundary where DB mutations, cascade/null/protect handling, and post-delete in-memory cleanup are coordinated.
  - For this requirement, only no-dependency fast path is allowed to carry in-memory PK-clearing semantics; other branches must not depend on that contract.

## Structural Contracts
- **No-new-in-memory-PK-dependency contract**
  - Input: any dependency-managed delete path (`on_delete` relationship graph present) or queryset `.delete()` bulk flow.
  - Rule: flows must not introduce dependency on instance `.pk` being `None` before/after internal operations.
- **Dependency-managed behavior contract**
  - Input: relation-managed object graph with configured `CASCADE`, `SET_NULL`, `PROTECT`, and protected/dependency variants.
  - Rule: traversal and DB operation ordering/signals for those relationships remain owned by collector internals and remain behaviorally unchanged.
- **Bulk-delete orchestration contract**
  - Input: `QuerySet.delete()` over related objects.
  - Rule: public API remains collector-driven; it should not encode a new local success/failure contract around in-memory identity mutation.

## Dependency-Direction Notes
- `Model.delete()` and `QuerySet.delete()` must depend on `Collector` (entry orchestration) but must not depend on collector-internal PK mutation behavior.
- `Collector` must continue to depend on:
  - SQL deletion primitives,
  - relation/metadata model descriptors (`_meta`, `_meta.fields`, related-object metadata),
  - transaction/signal utilities for lifecycle guarantees.
- `Collector` must not depend on specific PK-clearing behavior for dependency-managed or bulk paths.

## Integration-Seam Skeletons
- **Seam 1: Delegation seam**
  - `Model.delete()` and `QuerySet.delete()` continue to call the collector without local PK-state mutation branching.
- **Seam 2: Branch-separation seam**
  - `Collector.collect()` must preserve clear split between:
    - fast-delete eligibility evaluation,
    - related-object dependency collection.
- **Seam 3: Settlement seam**
  - `Collector.delete()` keeps existing dependency-managed settlement sequence intact.
  - Any future PK mutation work for no-dependency paths remains isolated to its own branch and not projected to dependency-managed/bulk branches.

## Readiness
- Requirement-to-architecture mapping is complete for all logical obligations in `DJ11179-005`.
- The structure identifies exact ownership and boundaries for implementation follow-through.
- One architecture artifact has been created: `docs/architecture/dj11179-005-preserve-dependency-managed-bulk-delete-semantics.md`.
