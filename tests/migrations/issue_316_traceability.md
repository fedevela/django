# Issue 316 Traceability Map

## Architecture artifact
- `tests/migrations/issue_316_architecture.md`

## Requirement: `FKEY-003`
- Obligation: After a PK RenameField, dependent FK `AlterField` operations that refresh explicit `to_field` targets must remain validly ordered and executable.
- Artifact: `tests/migrations/test_autodetector.py::AutodetectorTests.test_FKEY_003_rename_pk_and_dependent_fk_alterfield_plan_orders_pk_rename_before_to_field_target_update`
- Structural locus: `django/db/migrations/autodetector.py` (`generate_altered_fields`, `_sort_migrations`)
- Obligation: Generated migration plan must apply end-to-end without stale `to_field` relation resolution in the executor path.
- Artifact: `tests/migrations/test_executor.py::ExecutorTests.test_FKEY_003_rename_pk_dependent_alterfield_plan_executes_after_plan_sorting`
- Structural locus: `django/db/migrations/executor.py` (`_migrate_all_forwards`)
- Obligation: A stale `to_field='field_wrong'` under PK rename scenarios must fail early and deterministically on execution/replay.
- Artifact: `tests/migrations/test_executor.py::ExecutorTests.test_FKEY_003_wrong_to_field_reference_fails_early_during_execution_plan_replay`
- Structural locus: `django/db/migrations/loader.py` (`project_state`)
