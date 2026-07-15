# DJANGO11910-001: FK `to_field` normalization after PK rename

## Requirement-to-architecture map

- `DJANGO11910-001`  
  Primary-key rename on a target model must be reflected in generated
  migration deconstruction for dependent `ForeignKey(..., to_field=...)` fields.

## Owned logic locus and placement

- **Migration operation state propagation**  
  Owner: `django.db.migrations.operations.fields.RenameField.state_forwards`  
  Responsibility: mutate migration state model graph so every relation
  targeting the renamed model and explicitly naming `field_name` is updated to
  the new PK name before downstream code generation.

- **Autodetect field alteration normalization**  
  Owner: `django.db.migrations.autodetector.Autodetector.generate_altered_fields`  
  Responsibility: normalize stale FK deconstruction inputs from the incoming model
  state comparison so diffing/deconstruction does not emit legacy `to_field`.

- **Deconstruction + rendering boundary**  
  Owners: `django.db.migrations.writer.MigrationWriter` + `django.db.migrations.serializer.Serializer`  
  Responsibility: consume normalized state and emit migration artifacts; no extra
  rewriting should happen here for PK renames.

## Boundary and interface contracts

- `RenameField` boundary contract:
  - **Input**: model rename op context (`app_label`, `model_name_lower`, `old_name`,
    `new_name`)
  - **Output**: updated in-memory state (`state.models`), where any relation on
    `remote_field.model == renamed model` with explicit `remote_field.field_name ==
    old_name` is rewritten to `new_name`.
- `Autodetector` normalization contract:
  - **Input**: `self.renamed_fields` mapping and paired `old_field/new_field`
    descriptors during altered-field comparison.
  - **Output**: `new_field.remote_field.field_name` points at canonical PK name
    when `(renamed_model, old_to_field)` exists.
- `No-op contract`: if `field_name` is absent or no mapping exists, operation
  must not rewrite; behavior remains unchanged.

## Dependency direction

- `Model changes` ➜ `AutoDetector` (change diffing) ➜ `RenameField.state_forwards`
  state rewrites can be re-used by later operations.
- `RenameField` rewrites `state.models` ➜ `Autodetector` deep deconstruction
  consumes normalized field metadata.
- `Autodetector` comparisons ➜ migration code writer/rendering.

## Integration-seam stubs

- **FK Target Renaming seam (authoritative)**  
  Location: `generate_altered_fields` relation normalization branch before
  `deep_deconstruct(old_field) / deep_deconstruct(new_field)`.
- **State-wide Relation Rewrite seam (authoritative)**  
  Location: `RenameField.state_forwards` cross-model scan of
  `state.models` entries.

## Mapping of changed files to requirement

- `django/db/migrations/operations/fields.py` — requirement ownership and rewrite
  rule point for renamed PK effects in migration state.
- `django/db/migrations/autodetector.py` — requirement ownership and deconstruction
  canonicalization point for `to_field` generation.
- `tests/migrations/test_autodetector.py` — requirement ID registry and traceability
  anchors for this issue.
- `docs/architecture/django11910-001-fk-to-field-pk-rename.md` — this architecture
  artifact.

## Completion status (for this phase)

- All obligations from `DJANGO11910-001` have explicit architectural homes.
- Boundary/capability ownership and dependency flow are explicit.
- At least one architecture artifact created (`docs/architecture/django11910-001-fk-to-field-pk-rename.md`).
