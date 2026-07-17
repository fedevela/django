from django.db.migrations.utils import get_migration_name_timestamp
from django.db.transaction import atomic

from .exceptions import IrreversibleError


class Migration:
    """
    The base class for all migrations.

    Migration files will import this from django.db.migrations.Migration
    and subclass it as a class called Migration. It will have one or more
    of the following attributes:

     - operations: A list of Operation instances, probably from
       django.db.migrations.operations
     - dependencies: A list of tuples of (app_path, migration_name)
     - run_before: A list of tuples of (app_path, migration_name)
     - replaces: A list of migration_names

    Note that all migrations come out of migrations and into the Loader or
    Graph as instances, having been initialized with their app label and name.
    """

    # Operations to apply during this migration, in order.
    operations = []

    # Other migrations that should be run before this migration.
    # Should be a list of (app, migration_name).
    dependencies = []

    # Other migrations that should be run after this one (i.e. have
    # this migration added to their dependencies). Useful to make third-party
    # apps' migrations run after your AUTH_USER replacement, for example.
    run_before = []

    # Migration names in this app that this migration replaces. If this is
    # non-empty, this migration will only be applied if all these migrations
    # are not applied.
    replaces = []

    # Is this an initial migration? Initial migrations are skipped on
    # --fake-initial if the table or fields already exist. If None, check if
    # the migration has any dependencies to determine if there are dependencies
    # to tell if db introspection needs to be done. If True, always perform
    # introspection. If False, never perform introspection.
    initial = None

    # Whether to wrap the whole migration in a transaction. Only has an effect
    # on database backends which support transactional DDL.
    atomic = True

    def __init__(self, name, app_label):
        self.name = name
        self.app_label = app_label
        # Copy dependencies & other attrs as we might mutate them at runtime
        self.operations = list(self.__class__.operations)
        self.dependencies = list(self.__class__.dependencies)
        self.run_before = list(self.__class__.run_before)
        self.replaces = list(self.__class__.replaces)

    def __eq__(self, other):
        return (
            isinstance(other, Migration)
            and self.name == other.name
            and self.app_label == other.app_label
        )

    def __repr__(self):
        return "<Migration %s.%s>" % (self.app_label, self.name)

    def __str__(self):
        return "%s.%s" % (self.app_label, self.name)

    def __hash__(self):
        return hash("%s.%s" % (self.app_label, self.name))

    def mutate_state(self, project_state, preserve=True):
        """
        Take a ProjectState and return a new one with the migration's
        operations applied to it. Preserve the original object state by
        default and return a mutated state from a copy.
        """
        new_state = project_state
        if preserve:
            new_state = project_state.clone()

        for operation in self.operations:
            operation.state_forwards(self.app_label, new_state)
        return new_state

    def apply(self, project_state, schema_editor, collect_sql=False):
        """
        Take a project_state representing all migrations prior to this one
        and a schema_editor for a live database and apply the migration
        in a forwards order.

        Return the resulting project state for efficient reuse by following
        Migrations.
        """
        # Architecture integration boundary (GUID: MIG-003): Migration.apply()
        # owns ordered execution and the adjacent-state handoff. It depends on
        # the operation contract only; operation classes remain unaware of the
        # combined relationship transition and of one another.
        #
        # Operation ownership boundary (GUID: MIG-004): AlterUniqueTogether
        # owns the obsolete model-option and schema-constraint transition. Its
        # database boundary is the schema editor receiving old and new states.
        #
        # Operation ownership boundary (GUID: MIG-005): RemoveField owns the
        # old concrete field boundary and AddField owns the ManyToManyField
        # state/storage boundary. Migration.apply() composes these operations
        # but does not absorb their field or backend-specific responsibilities.
        # GUID: MIG-003 - Combined relationship transition application:
        # INPUT: the project/database state immediately preceding an ordered
        # AlterUniqueTogether, RemoveField, AddField(ManyToManyField) sequence.
        # FOR each operation, derive its next state before applying its database
        # change, and hand both adjacent states to that database operation.
        # REQUIRE: apply AlterUniqueTogether while the old concrete field still
        # identifies the obsolete constraint; then remove the concrete field;
        # then add the many-to-many field and its storage.
        # SUCCESS: exhaust the sequence without a constraint-count ValueError
        # and return the final state. FAILURE: propagate any operation error and
        # do not report the combined migration as successfully applied.
        #
        # GUID: MIG-004 - Obsolete uniqueness removal:
        # WHEN AlterUniqueTogether is current, transition the model option to
        # its target value, compare the old and target tuples, and request
        # deletion of every obsolete tuple before the concrete field is removed.
        # OUTPUT: subsequent states and schema inspection contain no obsolete
        # uniqueness constraint. FAILURE: if the old constraint cannot be
        # identified unambiguously, fail on this operation rather than advance.
        #
        # GUID: MIG-005 - Many-to-many state and database storage:
        # WHEN RemoveField is current, remove the old concrete field from state
        # and database storage. WHEN AddField is current, add the target
        # ManyToManyField to state and create its implicit through-table storage.
        # OUTPUT: the returned migration state marks the field many-to-many and
        # the database persists relationships through that table, not the old
        # concrete column. FAILURE: if either transition step fails, propagate
        # the error and do not expose a partially transitioned state as success.
        #
        # GUID: MIG-006 - Existing history remains usable:
        # INPUT: the state produced by all preceding historical migrations and
        # the next migration's stored operation sequence.
        # FOR each operation, use the standard adjacent-state handoff without
        # rewriting, replacing, or reinterpreting preceding migration files.
        # OUTPUT: prior migrations apply as before and their resulting state is
        # accepted as the starting state of the newly combined migration.
        # FAILURE PATH: propagate the first historical or combined-operation
        # error; never compensate by mutating an earlier migration definition.
        #
        # GUID: MIG-007 - Preserve unrelated schema and application data:
        # FOR each operation, derive old and next project states, then limit the
        # database handoff to that operation's declared model option or field.
        # REQUIRE: the constraint removal and field transition identify only
        # the obsolete tuple and converted relationship; unrelated fields,
        # relationships, constraints, tables, rows, and values receive no
        # transition. OUTPUT: all unrelated state and data pass through intact.
        # FAILURE PATH: if an operation cannot isolate its declared target,
        # propagate its error instead of issuing collateral schema or data work.
        #
        # GUID: MIG-008 - Supported-backend execution:
        # INPUT: the backend-provided schema editor and its transaction feature
        # flags. SELECT the existing atomic wrapper when the editor cannot make
        # DDL atomic; otherwise use its normal operation path. Delegate every
        # schema change through the editor's portable operation contract.
        # OUTPUT: the ordered transition completes without an out-of-band or
        # backend-specific repair handoff. FAILURE PATH: surface the backend
        # operation error and do not request a manual repair continuation.
        #
        # GUID: MIG-010 - Preserve the established two-migration sequence:
        # GIVEN migration A removes the obsolete constraint and migration B
        # later converts the relationship, apply A to completion and return its
        # state; then accept that state as B's input and apply B independently.
        # IF the operations are combined instead, preserve their stored order
        # within the single loop. OUTPUT: both representations remain applicable
        # in dependency order. FAILURE PATH: do not require adjacency within one
        # migration or recreate the removed constraint between migrations.
        for operation in self.operations:
            # If this operation cannot be represented as SQL, place a comment
            # there instead
            if collect_sql:
                schema_editor.collected_sql.append("--")
                schema_editor.collected_sql.append("-- %s" % operation.describe())
                schema_editor.collected_sql.append("--")
                if not operation.reduces_to_sql:
                    schema_editor.collected_sql.append(
                        "-- THIS OPERATION CANNOT BE WRITTEN AS SQL"
                    )
                    continue
                collected_sql_before = len(schema_editor.collected_sql)
            # Save the state before the operation has run
            old_state = project_state.clone()
            operation.state_forwards(self.app_label, project_state)
            # Run the operation
            atomic_operation = operation.atomic or (
                self.atomic and operation.atomic is not False
            )
            if not schema_editor.atomic_migration and atomic_operation:
                # Force a transaction on a non-transactional-DDL backend or an
                # atomic operation inside a non-atomic migration.
                with atomic(schema_editor.connection.alias):
                    operation.database_forwards(
                        self.app_label, schema_editor, old_state, project_state
                    )
            else:
                # Normal behaviour
                operation.database_forwards(
                    self.app_label, schema_editor, old_state, project_state
                )
            if collect_sql and collected_sql_before == len(schema_editor.collected_sql):
                schema_editor.collected_sql.append("-- (no-op)")
        return project_state

    def unapply(self, project_state, schema_editor, collect_sql=False):
        """
        Take a project_state representing all migrations prior to this one
        and a schema_editor for a live database and apply the migration
        in a reverse order.

        The backwards migration process consists of two phases:

        1. The intermediate states from right before the first until right
           after the last operation inside this migration are preserved.
        2. The operations are applied in reverse order using the states
           recorded in step 1.
        """
        # Construct all the intermediate states we need for a reverse migration
        to_run = []
        new_state = project_state
        # Phase 1
        for operation in self.operations:
            # If it's irreversible, error out
            if not operation.reversible:
                raise IrreversibleError(
                    "Operation %s in %s is not reversible" % (operation, self)
                )
            # Preserve new state from previous run to not tamper the same state
            # over all operations
            new_state = new_state.clone()
            old_state = new_state.clone()
            operation.state_forwards(self.app_label, new_state)
            to_run.insert(0, (operation, old_state, new_state))

        # Phase 2
        for operation, to_state, from_state in to_run:
            if collect_sql:
                schema_editor.collected_sql.append("--")
                schema_editor.collected_sql.append("-- %s" % operation.describe())
                schema_editor.collected_sql.append("--")
                if not operation.reduces_to_sql:
                    schema_editor.collected_sql.append(
                        "-- THIS OPERATION CANNOT BE WRITTEN AS SQL"
                    )
                    continue
                collected_sql_before = len(schema_editor.collected_sql)
            atomic_operation = operation.atomic or (
                self.atomic and operation.atomic is not False
            )
            if not schema_editor.atomic_migration and atomic_operation:
                # Force a transaction on a non-transactional-DDL backend or an
                # atomic operation inside a non-atomic migration.
                with atomic(schema_editor.connection.alias):
                    operation.database_backwards(
                        self.app_label, schema_editor, from_state, to_state
                    )
            else:
                # Normal behaviour
                operation.database_backwards(
                    self.app_label, schema_editor, from_state, to_state
                )
            if collect_sql and collected_sql_before == len(schema_editor.collected_sql):
                schema_editor.collected_sql.append("-- (no-op)")
        return project_state

    def suggest_name(self):
        """
        Suggest a name for the operations this migration might represent. Names
        are not guaranteed to be unique, but put some effort into the fallback
        name to avoid VCS conflicts if possible.
        """
        if self.initial:
            return "initial"

        raw_fragments = [op.migration_name_fragment for op in self.operations]
        fragments = [name for name in raw_fragments if name]

        if not fragments or len(fragments) != len(self.operations):
            return "auto_%s" % get_migration_name_timestamp()

        name = fragments[0]
        for fragment in fragments[1:]:
            new_name = f"{name}_{fragment}"
            if len(new_name) > 52:
                name = f"{name}_and_more"
                break
            name = new_name
        return name


class SwappableTuple(tuple):
    """
    Subclass of tuple so Django can tell this was originally a swappable
    dependency when it reads the migration file.
    """

    def __new__(cls, value, setting):
        self = tuple.__new__(cls, value)
        self.setting = setting
        return self


def swappable_dependency(value):
    """Turn a setting value into a dependency."""
    return SwappableTuple((value.split(".", 1)[0], "__first__"), value)
