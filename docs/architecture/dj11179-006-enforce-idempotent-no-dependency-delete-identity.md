# DJ11179-006 — Ensure repeated no-dependency instance delete calls are identity-idempotent

## Requirement
- **GUID:** `DJ11179-006`
- **Scope:** after a successful no-dependency delete on a persisted instance, repeated `Model.delete()` invocations on the same in-memory object must remain identity-safe (`pk` must stay `None`) and must not reintroduce prior primary key state.

## Requirement-to-Architecture Map
- `DJ11179-006` → `django/db/models/base.py:Model.delete()`
  - Pressure: preserve public delete API semantics as a delegation boundary and add a short-circuit for already-cleared instances to keep repeated calls safe.
- `DJ11179-006` → `django/db/models/deletion.py:Collector.delete()` (`single-instance fast-delete branch`)
  - Pressure: treat already-cleared singleton instances as already-complete; short-circuit fast-delete execution while keeping in-memory identity as `None`.
- `DJ11179-006` → `tests/delete_regress/tests.py:DeleteNoDependencyIdempotencyTraceabilityTests`
  - Pressure: map the three obligation checks (`*_keeps_pk_none`, `*_does_not_resurrect_pk`, `*_return_paths_preserve_none_pk`) to the two delegation/seam boundaries.

## Placement and Ownership
- **Primary owners:**
  - `Model.delete()` in `django/db/models/base.py` owns API-level invocation semantics and idempotent handling for already-cleared instances.
  - `Collector.delete()` in `django/db/models/deletion.py` owns deletion-settlement decisions for no-dependency fast-delete flows.
- **Dependency-managed out-of-scope owners:**
  - relationship traversal, `on_delete` policy handling, and queryset bulk-delete orchestration remain owned by their existing branches and are not part of this requirement’s structural target.

## Boundaries
- **Boundary A — API invocation boundary (`Model.delete()`):**
  - Input: repeated delete invocation on same instance after first success.
  - Rule: if `_state.adding is False` and `pk is None`, return success-path semantics locally without issuing another collector cycle.
  - Outcome contract: keep `pk` as `None` and avoid reviving identity state.
- **Boundary B — Fast-delete singleton boundary (`Collector.delete()`):**
 - Input: `self.data` has one model and one collected instance.
 - Rule: detect `instance.pk is None` before mutation branch selection and treat as no-op-complete.
 - Outcome contract: return deletion count/result without SQL mutation that could imply resurrection behavior.
- **Boundary C — Settlement boundary:**
  - Existing shared settlement path remains unchanged for this requirement; no new dependency on prior successful/failed fast-delete attempt states is introduced.

## Structural Contracts
- **Identity-Idempotence Contract (re-invocation):**
  - Input: in-memory object where `pk is None`, `_state.adding is False`, and previous operation was successful no-dependency delete.
  - Constraint: second/third call keeps identity cleared; no transition back to previous PK value.
- **No-Resurrection Contract (post-return):**
  - Input: repeated no-dependency delete call after successful clear.
  - Constraint: any returned delete count path must not mutate PK from `None`.
- **Safety/compatibility Contract:**
  - Unsaved instances (`_state.adding is True`) remain outside this requirement and continue to follow pre-existing assertion behavior.

## Dependency-Direction Notes
- `Model.delete()` depends on router/deletion orchestration and `Collector` only at an invocation boundary.
- `Collector.delete()` depends on SQL deletion primitives and metadata (`_meta.pk.attname`) for existing successful-clear transitions; this requirement adds no new cross-module dependencies.
- Both boundaries must avoid depending on each other’s internal state mutation details beyond the idempotence signal (`pk is None` and `_state.adding is False`).

## Integration-Seam Skeletons
- **Seam 1: Re-entry guard at `Model.delete()`**
  - A pre-collector guard branch for already-cleared, persisted objects.
  - Keeps repeated deletion idempotent and preserves caller-visible identity contract.
- **Seam 2: Re-entry guard at `Collector.delete()` singleton fast path**
  - A pre-mutation return early branch when singleton `instance.pk is None`.
  - Maintains no-SQL outcome for re-invocations and blocks PK resurrection from branch reuse.
- **Seam 3: Regression-semantics seam**
  - Existing tests in `DeleteNoDependencyIdempotencyTraceabilityTests` remain aligned to requirement obligations and can be expanded to behavior assertions in implementation phase.

## Completion Status
- All architecture obligations under `DJ11179-006` are mapped to explicit repository loci.
- At least one architecture artifact has been created: this file.
- Structural placement, ownership boundaries, integration seams, and dependency direction are explicit for implementation follow-through.
