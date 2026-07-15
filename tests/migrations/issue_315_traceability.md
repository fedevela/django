# Issue 315 Traceability Map

## Requirement: `FKEY-001`
- Obligation: FK `to_field` emitted in generated migration operations should use post-rename PK name.
- Artifact: `tests/migrations/test_autodetector.py::AutodetectorTests.test_FKEY_001_rename_pk_updates_fk_to_field_in_generated_ops`

## Requirement: `FKEY-002`
- Obligation: Migration state/deconstruction output must persist renamed `to_field` consistently.
- Artifact: `tests/migrations/test_operations.py::OperationTests.test_FKEY_002_rename_field_state_remaps_fk_to_field_metadata`

## Requirement: `FKEY-007`
- Obligation: Repeatable migration-state checks reject stale/pre-rename `to_field` references.
- Artifact: `tests/migrations/test_loader.py::LoaderTests.test_FKEY_007_repeatable_state_check_rejects_stale_fk_to_field`
