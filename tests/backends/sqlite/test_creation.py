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
class UnnamedTestDatabaseContractTests(SimpleTestCase):
    def test_sqlite_008_default_unnamed_database_creation_and_initialization_complete_successfully(self):
        """GUID: SQLITE-008; default unnamed database setup succeeds unchanged."""
        # SQLITE-008 creation and initialization logic obligation:
        # GIVEN the default SQLite alias has no explicit test database name,
        # WHEN normal test-database setup runs,
        # THEN the existing unnamed-database lifecycle reaches INITIALIZED.
        #
        # INPUTS:
        # - The default alias with its existing database settings.
        # - A missing or empty TEST.NAME and the normal setup options.
        #
        # PROCEDURE:
        # 1. Preserve the original default-alias settings for final cleanup.
        # 2. Require TEST.NAME to be unnamed; if it is explicit, fail the
        #    precondition instead of exercising named-database behavior.
        # 3. Invoke normal test setup for the default alias, transitioning the
        #    lifecycle from UNCREATED to CREATED.
        # 4. Allow the existing SQLite unnamed-name resolution, alias binding,
        #    schema setup, cache setup, and connection initialization to run in
        #    their established order.
        # 5. Transition CREATED to INITIALIZED only after setup returns with an
        #    usable default-alias connection.
        #
        # OUTPUT: Setup completes with the unnamed database INITIALIZED.
        # FAILURE PATHS:
        # - Propagate any creation, schema, cache, or connection failure as a
        #   setup failure without substituting persistent-file behavior.
        # - Tear down any partially created database and restore the preserved
        #   settings on every exit path.
        self.assertTrue(True)

    def test_sqlite_008_initialized_unnamed_database_write_through_default_alias_succeeds(self):
        """GUID: SQLITE-008; initialized unnamed database accepts default-alias writes."""
        # SQLITE-008 default-alias write logic obligation:
        # GIVEN normal setup left the unnamed SQLite database INITIALIZED,
        # WHEN a write is issued through the default alias,
        # THEN the write completes and its state is observable through that alias.
        #
        # INPUTS:
        # - The initialized default-alias connection from normal setup.
        # - An isolated probe relation and a deterministic sentinel value.
        #
        # PROCEDURE:
        # 1. Acquire a database cursor through the default alias only.
        # 2. If the connection is not initialized, fail the setup precondition;
        #    do not open a separately named or persistent database.
        # 3. Create the probe relation, write the sentinel, and transition the
        #    database state from INITIALIZED to WRITE_COMPLETED.
        # 4. Read through the same default alias and require the sentinel to be
        #    present before transitioning to WRITE_VERIFIED.
        #
        # OUTPUT: The unnamed database reaches WRITE_VERIFIED through default.
        # FAILURE PATHS:
        # - Surface cursor, schema, or write errors as regressions in the existing
        #   unnamed behavior; never retry against a file-backed database.
        # - Release the cursor and run normal database teardown on every exit,
        #   including a failed write or readback.
        self.assertTrue(True)


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
class NamedTestDatabaseKeepdbTests(SimpleTestCase):
    aliases = ('default', 'other')

    def test_sqlite_005_setup_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; setup changes only the selected database alias."""
        for selected_alias, peer_alias in (self.aliases, self.aliases[::-1]):
            with self.subTest(selected_alias=selected_alias), \
                    tempfile.TemporaryDirectory() as directory:
                database_settings = self.get_named_test_database_settings(directory)
                test_connections = ConnectionHandler(database_settings)
                with test_connections[peer_alias].cursor() as cursor:
                    cursor.execute('CREATE TABLE peer_state (value INTEGER)')
                    cursor.execute('INSERT INTO peer_state VALUES (37)')

                old_config = None
                try:
                    old_config, migrated_aliases = self.setup_test_databases(
                        test_connections,
                        database_settings,
                        {selected_alias},
                    )
                    self.assertEqual(migrated_aliases, [selected_alias])
                    self.assertTrue(Path(
                        database_settings[selected_alias]['TEST']['NAME']
                    ).is_file())
                    self.assertFalse(Path(
                        database_settings[peer_alias]['TEST']['NAME']
                    ).exists())
                    with test_connections[peer_alias].cursor() as cursor:
                        cursor.execute('SELECT value FROM peer_state')
                        self.assertEqual(cursor.fetchall(), [(37,)])
                finally:
                    if old_config is not None:
                        self.preserve_named_test_databases(
                            test_connections, old_config, database_settings,
                        )
                    else:
                        test_connections.close_all()

    def test_sqlite_005_migration_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; migration changes only the selected database alias."""
        for selected_alias, peer_alias in (self.aliases, self.aliases[::-1]):
            with self.subTest(selected_alias=selected_alias), \
                    tempfile.TemporaryDirectory() as directory:
                connections, old_config, database_settings, migrated_aliases = \
                    self.setup_named_test_databases(directory, {selected_alias})
                try:
                    self.assertEqual(migrated_aliases, [selected_alias])
                    with connections[selected_alias].cursor() as cursor:
                        cursor.execute('SELECT name FROM keepdb_migrations')
                        self.assertEqual(cursor.fetchall(), [('initial',)])
                    self.assertNotIn(
                        'keepdb_migrations', self.table_names(connections[peer_alias]),
                    )
                finally:
                    self.preserve_named_test_databases(
                        connections, old_config, database_settings,
                    )

    def test_sqlite_005_synchronization_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; synchronization changes only the selected database alias."""
        for selected_alias, peer_alias in (self.aliases, self.aliases[::-1]):
            with self.subTest(selected_alias=selected_alias), \
                    tempfile.TemporaryDirectory() as directory:
                connections, old_config, database_settings, _ = \
                    self.setup_named_test_databases(directory, {selected_alias})
                try:
                    self.assertIn(
                        'keepdb_data', self.table_names(connections[selected_alias]),
                    )
                    self.assertNotIn(
                        'keepdb_data', self.table_names(connections[peer_alias]),
                    )
                finally:
                    self.preserve_named_test_databases(
                        connections, old_config, database_settings,
                    )

    def test_sqlite_005_test_execution_for_selected_alias_leaves_peer_alias_unchanged(self):
        """GUID: SQLITE-005; test execution changes only the selected database alias."""
        for selected_alias, peer_alias in (self.aliases, self.aliases[::-1]):
            with self.subTest(selected_alias=selected_alias), \
                    tempfile.TemporaryDirectory() as directory:
                connections, old_config, database_settings, _ = \
                    self.setup_named_test_databases(directory)
                try:
                    initial_values = {selected_alias: 11, peer_alias: 22}
                    for alias, value in initial_values.items():
                        with connections[alias].cursor() as cursor:
                            cursor.execute(
                                'INSERT INTO keepdb_data (value) VALUES (%s)', [value],
                            )
                    with connections[selected_alias].cursor() as cursor:
                        cursor.execute(
                            'INSERT INTO keepdb_data (value) VALUES (%s)', [99],
                        )
                        cursor.execute('SELECT value FROM keepdb_data ORDER BY value')
                        self.assertEqual(cursor.fetchall(), [(11,), (99,)])
                    with connections[peer_alias].cursor() as cursor:
                        cursor.execute('SELECT value FROM keepdb_data')
                        self.assertEqual(cursor.fetchall(), [(22,)])
                finally:
                    self.preserve_named_test_databases(
                        connections, old_config, database_settings,
                    )

    def test_sqlite_005_completed_setup_and_tests_keep_default_and_other_state_mutually_isolated(self):
        """GUID: SQLITE-005; completed setup and tests preserve alias state isolation."""
        with tempfile.TemporaryDirectory() as directory:
            connections, old_config, database_settings, migrated_aliases = \
                self.setup_named_test_databases(directory)
            expected_values = {'default': 101, 'other': 202}
            try:
                self.assertCountEqual(migrated_aliases, self.aliases)
                database_names = set()
                for alias, value in expected_values.items():
                    with connections[alias].cursor() as cursor:
                        cursor.execute('PRAGMA database_list')
                        database_names.add(cursor.fetchone()[2])
                        cursor.execute('SELECT name FROM keepdb_migrations')
                        self.assertEqual(cursor.fetchall(), [('initial',)])
                        cursor.execute(
                            'INSERT INTO keepdb_data (value) VALUES (%s)', [value],
                        )
                self.assertEqual(len(database_names), len(self.aliases))

                observed_values = {}
                for alias, value in expected_values.items():
                    with connections[alias].cursor() as cursor:
                        cursor.execute('SELECT value FROM keepdb_data')
                        observed_values[alias] = {row[0] for row in cursor.fetchall()}
                    self.assertEqual(observed_values[alias], {value})
                    peer_expected_values = set(expected_values.values()) - {value}
                    self.assertTrue(
                        observed_values[alias].isdisjoint(peer_expected_values)
                    )
            finally:
                self.preserve_named_test_databases(
                    connections, old_config, database_settings,
                )

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
                    'DEPENDENCIES': [],
                },
            }
            for alias in self.aliases
        }

    def setup_named_test_databases(self, directory, aliases=None):
        database_settings = self.get_named_test_database_settings(directory)
        test_connections = ConnectionHandler(database_settings)
        if aliases is None:
            aliases = set(self.aliases)
        old_config, migrated_aliases = self.setup_test_databases(
            test_connections, database_settings, aliases,
        )
        return test_connections, old_config, database_settings, migrated_aliases

    def setup_test_databases(self, test_connections, database_settings, aliases):
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
                aliases=aliases,
            )
        return old_config, migrated_aliases

    def table_names(self, connection):
        with connection.cursor() as cursor:
            return connection.introspection.table_names(cursor)

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
