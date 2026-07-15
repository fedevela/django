# SQLMigrate Transaction Output Gate Architecture

Issue: SQLMIGRATE-001, SQLMIGRATE-004

## Requirement-to-architecture mapping

- `SQLMIGRATE-001`
  - Obligation: gate `self.output_transaction` by atomicity **and** rollback-capable DDL.
  - Command locus: `django/core/management/commands/sqlmigrate.py` in `Command.handle` near assignment to `self.output_transaction`.
  - Existing traceability map: `tests/migrations/test_commands.py` (`SQLMIGRATE_VERIFICATION_ARTIFACTS`).

- `SQLMIGRATE-004`
  - Obligation: keep non-atomic migrations unwrapped regardless of backend capability.
  - Command locus: same as above.

## Ownership and boundaries

- Owner: `django.core.management.commands.sqlmigrate.Command` (management command boundary).
- Decision boundary: output-format decision is command-local and depends only on:
  - migration metadata (`migration.atomic`)
  - connection capabilities (`connection.features.can_rollback_ddl`)
- No executor internals or schema editor internals ownership change is required.

## Contract / interface shape

- **Boundary contract (`SQLMIGRATE-OUTPUT-GATE`)**:
  - Input: `migration` object and active `connection`.
  - Output: boolean `should_emit_transaction_wrapper`.
  - Rule: `should_emit_transaction_wrapper = migration.atomic and connection.features.can_rollback_ddl`.
  - Effect:
    - `True` => command writes BEGIN/COMMIT markers.
    - `False` => command writes unwrapped SQL.

## Dependency direction

- `sqlmigrate.Command.handle` currently depends on `MigrationExecutor` for plan/SQL generation and on `connections[...]` for backend feature capability.
- This new gate decision must remain a single dependency sink from command layer into backend capability surface and must not feed back into migration graph/execution internals.

## Integration seam (implementation skeleton)

- Current integration seam remains in `Command.handle`:
  - `self.output_transaction = migration.atomic` (currently atomic-only behavior)
- Target architecture-ready transition:
  - Replace this assignment with a gate function/local seam that applies `SQLMIGRATE-OUTPUT-GATE` and remains confined to command-layer decision logic.
  - Keep all other SQL-generation behavior (`executor.collect_sql(plan)`) untouched.

## Topology impact

- No new modules/files required for runtime.
- One new architecture artifact file added: this document.
- Implementation-impact is isolated to a single command decision point.

## Completion notes

- All traced obligations are mapped to a single command-seam locus.
- The decision is structurally expressed as an ownership boundary plus explicit contract.
- No behavioral/runtime changes introduced in this phase.
