# Issue 315 Architecture (FKEY-001 / FKEY-002 / FKEY-007)

## Scope anchors
- Canonical requirements: `FKEY-001`, `FKEY-002`, `FKEY-007`
- Goal: place deterministic rename-to-field logic into stable ownership boundaries and explicit seams before implementation.

## Requirement-to-architecture map
- `FKEY-001` → migration planning seam in `django/db/migrations/autodetector.py`
  - `Autodetector.generate_renamed_fields`
  - `Autodetector.generate_altered_fields`
- `FKEY-002` → state serialization seam in `django/db/migrations/operations/fields.py`
  - `RenameField.state_forwards`
- `FKEY-007` → repeatable-state validation seam in `django/db/migrations/loader.py`
  - `Loader.project_state`

## Ownership and boundaries
- `autodetector.py` owns **change detection and operation synthesis** boundaries:
  - Input: `from_state`, `to_state`, `renamed_models`, `renamed_fields`, and field deconstructions.
  - Output: normalized migration ops and rename metadata.
  - Constraint: must never mutate DB; deterministic in-memory planning only.
- `operations/fields.py` owns **migration state mutation** boundaries:
  - Input: `ProjectState`, `RenameField` request, and existing model graph.
  - Output: consistent in-memory FK metadata (`field_name`, `to_fields`) aligned to the renamed local key.
  - Constraint: in-band state continuity; failures must surface as existing `FieldDoesNotExist` or relation-lookup exceptions.
- `loader.py` owns **state replay and repeatable consistency boundary**:
  - Input: migration graph nodes and reconstruction flags.
  - Output: replayed `ProjectState` that is accepted only when referenced FK targets remain resolvable.
  - Constraint: stale `to_field` targets must be rejected through normal deterministic state consumption.

## Dependency direction
1. `autodetector.py` produces migration operations -> consumed by migration state serialization logic.
2. `operations/fields.py` enforces key-level FK metadata consistency on `RenameField.state_forwards` updates.
3. `loader.py` reconstructs/dependencies state via `graph.make_state(...)`, so stale metadata reaches failure at replay/validation time.

## Integration seams and contracts
- **Rename-translation seam** (`autodetector.py`):
  - Contract: before deconstruction compare, translate foreign references through `renamed_models` and `renamed_fields`.
  - Boundary type: pure algorithmic transformation of migration candidates.
- **FK-metadata propagation seam** (`operations/fields.py`):
  - Contract: when a local PK/target field is renamed, update all dependent remote metadata (`field_name`, `to_fields`) in `ProjectState`.
  - Boundary type: model-state mutation in canonical migration operation execution path.
- **Repeatability validation seam** (`loader.py`):
  - Contract: replayed state is the source of truth; unresolved FK targets fail deterministically during state consumption.
  - Boundary type: loader/project graph convergence checkpoint.

## Structural placeholders needed for implementation
- Keep current file-level loci and comments, but treat the three comment sites as contract anchors.
- Add behavior in implementation behind existing signatures; no API additions required.
- Preserve requirement IDs at loci comments for traceability continuity.

## Completion status
- At least one architecture artifact created.
- Every logic obligation mapped to a concrete module/function seam.
- Structural changes are requirement-traceable and explicitly scoped to migration architecture.
