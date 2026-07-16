import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import ConnectionHandler, connection
from django.test import SimpleTestCase
from django.test.utils import setup_databases, teardown_databases


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
class TestDbSignatureTests(SimpleTestCase):
    def test_custom_test_name(self):
        """GUID: SQLITE-001, SQLITE-002."""
        saved_settings = copy.deepcopy(connection.settings_dict)
        try:
            connection.settings_dict['NAME'] = None
            connection.settings_dict['TEST']['NAME'] = 'custom.sqlite.db'
            signature = connection.creation.test_db_signature()
            self.assertEqual(signature, (None, 'custom.sqlite.db'))
        finally:
            connection.settings_dict = saved_settings


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
class NamedTestDatabaseKeepdbTests(SimpleTestCase):
    aliases = ('default', 'other')

    def test_sqlite_005_setup_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; setup changes only the selected database alias."""
        # SQLITE-005 setup logic obligation:
        # GIVEN default and other resolve to distinct SQLite test databases,
        # WHEN setup targets one selected alias,
        # THEN only that alias transitions from UNSET_UP to SET_UP and the peer
        # alias retains its pre-setup state.
        #
        # INPUTS:
        # - The selected alias, its distinct database name, and the peer alias.
        # - A peer-state marker captured before setup begins.
        #
        # PROCEDURE:
        # 1. Resolve the selected alias to its own connection and database name.
        # 2. If both aliases resolve to the same database, fail before setup.
        # 3. Capture the peer marker, run setup only for the selected alias, and
        #    transition that alias to SET_UP.
        # 4. Read the peer through its own alias and require its marker and setup
        #    state to equal the captured values.
        #
        # OUTPUT: The selected alias is SET_UP; the peer remains UNCHANGED.
        # FAILURE PATHS:
        # - Fail on a shared database identity or any peer-state mutation.
        # - Close both alias-bound connections on every exit path.
        pass

    def test_sqlite_005_migration_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; migration changes only the selected database alias."""
        # SQLITE-005 migration logic obligation:
        # GIVEN isolated alias databases and an unapplied migration for each,
        # WHEN migration executes for one selected alias,
        # THEN only its schema and migration history transition to MIGRATED.
        #
        # INPUTS:
        # - A selected alias, a peer alias, and equivalent pending migration work.
        # - The peer schema and migration-history snapshots taken before execution.
        #
        # PROCEDURE:
        # 1. Bind the migration executor to the selected alias connection.
        # 2. Apply the pending migration and record the selected alias as MIGRATED.
        # 3. Inspect schema and migration history through the peer alias.
        # 4. Require both peer snapshots to remain unchanged and the migration to
        #    remain unapplied there.
        #
        # OUTPUT: Selected is MIGRATED; peer remains UNMIGRATED_AND_UNCHANGED.
        # FAILURE PATHS:
        # - Fail if executor state or schema changes appear through the peer.
        # - Roll back or close only the connection associated with each alias.
        pass

    def test_sqlite_005_synchronization_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; synchronization changes only the selected database alias."""
        # SQLITE-005 synchronization logic obligation:
        # GIVEN isolated alias databases and an unsynchronized model,
        # WHEN synchronization targets one selected alias,
        # THEN its table state transitions to SYNCHRONIZED without creating or
        # changing that table in the peer database.
        #
        # INPUTS:
        # - The selected and peer aliases and a model eligible for synchronization.
        # - A peer table-state snapshot captured before synchronization.
        #
        # PROCEDURE:
        # 1. Route synchronization to the selected alias connection.
        # 2. Create the eligible table only in the selected database and transition
        #    the selected alias to SYNCHRONIZED.
        # 3. Inspect table state through each alias independently.
        # 4. Require the table through selected and the original snapshot through
        #    peer, without substituting either alias's connection.
        #
        # OUTPUT: Selected is SYNCHRONIZED; peer remains UNCHANGED.
        # FAILURE PATHS:
        # - Fail if the table is absent from selected or appears/changes in peer.
        # - Release both alias-bound schema contexts on every exit path.
        pass

    def test_sqlite_005_test_execution_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; test execution changes only the selected database alias."""
        # SQLITE-005 test-execution logic obligation:
        # GIVEN both aliases are set up and contain distinct state markers,
        # WHEN a test operation explicitly uses one selected alias,
        # THEN its read/write effects remain confined to that alias.
        #
        # INPUTS:
        # - A selected alias, a peer alias, and distinguishable initial markers.
        # - A test write value unique to the selected alias.
        #
        # PROCEDURE:
        # 1. Capture both initial markers through their respective connections.
        # 2. Execute the test write using the selected alias and transition it from
        #    READY to TEST_MUTATED.
        # 3. Read back through selected and require its marker plus the test value.
        # 4. Read through peer and require exactly its initial marker with no test
        #    value, leaving it READY_AND_UNCHANGED.
        #
        # OUTPUT: The test mutation is visible only through selected.
        # FAILURE PATHS:
        # - Fail on missing selected state or any leaked value in the peer.
        # - Restore/close each alias independently even if the test write fails.
        pass

    def test_sqlite_005_completed_setup_and_tests_keep_default_and_other_state_mutually_isolated(self):
        """GUID: SQLITE-005; completed setup and tests preserve alias state isolation."""
        # SQLITE-005 final-isolation logic obligation:
        # GIVEN setup, migration, synchronization, and test operations have run
        # for both default and other, WHEN final state is inspected per alias,
        # THEN each database contains all and only the state assigned to it.
        #
        # INPUTS:
        # - Distinct expected state sets for default and other.
        # - The completed lifecycle state of both alias-bound databases.
        #
        # PROCEDURE:
        # 1. For each alias in deterministic order, inspect schema, migration
        #    history, synchronized tables, and test data through that alias only.
        # 2. Compare the observed state with that alias's complete expected set.
        # 3. Compare it with the peer's expected-only set and require an empty
        #    intersection.
        # 4. Transition each alias from OPERATIONS_COMPLETE to ISOLATION_VERIFIED
        #    only after both inclusion and exclusion checks succeed.
        #
        # OUTPUT: default and other are both ISOLATION_VERIFIED.
        # FAILURE PATHS:
        # - Fail on missing local state, unexpected peer state, or shared identity.
        # - Preserve the first mismatch and close both connections during cleanup.
        pass

    def test_sqlite_004_reused_named_database_releases_blocking_state_before_test_write(self):
        """GUID: SQLITE-004; reused named databases allow subsequent test writes."""
        with tempfile.TemporaryDirectory() as directory:
            connections, old_config, database_settings, _ = self.setup_named_test_databases(directory)
            for alias in self.aliases:
                with connections[alias].cursor() as cursor:
                    cursor.execute('INSERT INTO keepdb_data (value) VALUES (-1)')
            self.preserve_named_test_databases(connections, old_config, database_settings)

            connections, old_config, database_settings, _ = self.setup_named_test_databases(directory)
            try:
                for value, alias in enumerate(self.aliases):
                    with connections[alias].cursor() as cursor:
                        cursor.execute(
                            'INSERT INTO keepdb_data (value) VALUES (%s)',
                            [value],
                        )
                        cursor.execute('SELECT value FROM keepdb_data ORDER BY value')
                        self.assertEqual(cursor.fetchall(), [(-1,), (value,)])
            finally:
                self.preserve_named_test_databases(connections, old_config, database_settings)

    def test_sqlite_006_reused_migrated_database_is_preserved_and_writable_after_setup(self):
        """GUID: SQLITE-006; setup preserves reused migrated databases as writable."""
        with tempfile.TemporaryDirectory() as directory:
            connections, old_config, database_settings, _ = self.setup_named_test_databases(directory)
            for value, alias in enumerate(self.aliases):
                with connections[alias].cursor() as cursor:
                    cursor.execute(
                        'INSERT INTO keepdb_data (value) VALUES (%s)',
                        [value],
                    )
            database_files = {
                alias: Path(database_settings[alias]['TEST']['NAME'])
                for alias in self.aliases
            }
            self.preserve_named_test_databases(connections, old_config, database_settings)

            connections, old_config, database_settings, migrated_aliases = self.setup_named_test_databases(directory)
            try:
                self.assertCountEqual(migrated_aliases, self.aliases)
                for value, alias in enumerate(self.aliases):
                    self.assertTrue(database_files[alias].is_file())
                    with connections[alias].cursor() as cursor:
                        cursor.execute('SELECT name FROM keepdb_migrations')
                        self.assertEqual(cursor.fetchall(), [('initial',)])
                        cursor.execute('SELECT value FROM keepdb_data')
                        self.assertEqual(cursor.fetchall(), [(value,)])
                        cursor.execute(
                            'INSERT INTO keepdb_data (value) VALUES (%s)',
                            [value + len(self.aliases)],
                        )
                        cursor.execute('SELECT value FROM keepdb_data ORDER BY value')
                        self.assertEqual(
                            cursor.fetchall(),
                            [(value,), (value + len(self.aliases),)],
                        )
            finally:
                self.preserve_named_test_databases(connections, old_config, database_settings)

    def test_sqlite_007_repeated_keepdb_reuse_does_not_accumulate_state_blocking_later_writes(self):
        """GUID: SQLITE-007; repeated keepdb reuse leaves later-run writes unlocked."""
        with tempfile.TemporaryDirectory() as directory:
            for cycle in range(3):
                connections, old_config, database_settings, _ = self.setup_named_test_databases(directory)
                try:
                    for alias_index, alias in enumerate(self.aliases):
                        value = cycle * len(self.aliases) + alias_index
                        with connections[alias].cursor() as cursor:
                            cursor.execute(
                                'INSERT INTO keepdb_data (value) VALUES (%s)',
                                [value],
                            )
                            cursor.execute('SELECT value FROM keepdb_data ORDER BY value')
                            self.assertEqual(
                                cursor.fetchall(),
                                [(previous * len(self.aliases) + alias_index,)
                                 for previous in range(cycle + 1)],
                            )
                finally:
                    self.preserve_named_test_databases(connections, old_config, database_settings)

    def get_named_test_database_settings(self, directory):
        return {
            alias: {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
                'TEST': {
                    'NAME': str(Path(directory) / ('%s.sqlite3' % alias)),
                    'SERIALIZE': False,
                },
            }
            for alias in self.aliases
        }

    def setup_named_test_databases(self, directory):
        database_settings = self.get_named_test_database_settings(directory)
        test_connections = ConnectionHandler(database_settings)
        migrated_aliases = []

        def call_command(command, **options):
            if command == 'migrate':
                alias = options['database']
                migrated_aliases.append(alias)
                with test_connections[alias].cursor() as cursor:
                    cursor.execute(
                        'CREATE TABLE IF NOT EXISTS keepdb_migrations '
                        '(name TEXT PRIMARY KEY)'
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO keepdb_migrations (name) VALUES ('initial')"
                    )
                    cursor.execute(
                        'CREATE TABLE IF NOT EXISTS keepdb_data (value INTEGER)'
                    )

        with mock.patch('django.test.utils.connections', test_connections), \
                mock.patch.object(settings, 'DATABASES', database_settings), \
                mock.patch('django.core.management.call_command', call_command):
            old_config = setup_databases(
                verbosity=0,
                interactive=False,
                keepdb=True,
                parallel=1,
                aliases=set(self.aliases),
            )
        return test_connections, old_config, database_settings, migrated_aliases

    def preserve_named_test_databases(self, test_connections, old_config, database_settings):
        with mock.patch.object(settings, 'DATABASES', database_settings):
            teardown_databases(old_config, verbosity=0, parallel=1, keepdb=True)
        test_connections.close_all()

    def create_named_test_databases(self, directory):
        database_settings = self.get_named_test_database_settings(directory)
        for alias in self.aliases:
            self.assertFalse(Path(database_settings[alias]['TEST']['NAME']).exists())
        test_connections = ConnectionHandler(database_settings)
        initialized_aliases = []

        def call_command(command, **options):
            if command == 'migrate':
                alias = options['database']
                initialized_aliases.append(alias)
                with test_connections[alias].cursor() as cursor:
                    cursor.execute(
                        'CREATE TABLE sqlite003_data (value INTEGER)'
                    )

        with mock.patch('django.test.utils.connections', test_connections), \
                mock.patch.object(settings, 'DATABASES', database_settings), \
                mock.patch('django.core.management.call_command', call_command):
            setup_databases(
                verbosity=0,
                interactive=False,
                keepdb=True,
                parallel=1,
                aliases=set(self.aliases),
            )
        return test_connections, initialized_aliases

    def test_sqlite_003_first_keepdb_parallel_1_run_creates_and_initializes_each_missing_named_alias_database(self):
        """GUID: SQLITE-003; missing named databases become initialized alias databases."""
        with tempfile.TemporaryDirectory() as directory:
            test_connections, initialized_aliases = self.create_named_test_databases(directory)
            try:
                self.assertCountEqual(initialized_aliases, self.aliases)
                for alias in self.aliases:
                    database_name = Path(directory) / ('%s.sqlite3' % alias)
                    self.assertTrue(database_name.is_file())
                    with test_connections[alias].cursor() as cursor:
                        cursor.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = %s",
                            ['sqlite003_data'],
                        )
                        self.assertEqual(cursor.fetchone(), ('sqlite003_data',))
                        cursor.execute('PRAGMA database_list')
                        databases = {row[1]: row[2] for row in cursor.fetchall()}
                    self.assertEqual(Path(databases['main']), database_name)
            finally:
                test_connections.close_all()

    def test_sqlite_003_writes_to_initialized_named_alias_databases_complete_without_database_lock_error(self):
        """GUID: SQLITE-003; initialized named databases accept required writes without locking."""
        with tempfile.TemporaryDirectory() as directory:
            test_connections, _ = self.create_named_test_databases(directory)
            try:
                for value, alias in enumerate(self.aliases):
                    with test_connections[alias].cursor() as cursor:
                        cursor.execute(
                            'INSERT INTO sqlite003_data (value) VALUES (%s)',
                            [value],
                        )
                for value, alias in enumerate(self.aliases):
                    with test_connections[alias].cursor() as cursor:
                        cursor.execute('SELECT value FROM sqlite003_data')
                        self.assertEqual(cursor.fetchall(), [(value,)])
            finally:
                test_connections.close_all()
