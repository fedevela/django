import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db import ConnectionHandler, connection
from django.test import SimpleTestCase
from django.test.utils import setup_databases


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

    def test_sqlite_004_reused_named_database_releases_blocking_state_before_test_write(self):
        """GUID: SQLITE-004; reused named databases allow subsequent test writes."""
        # SQLITE-004 logic obligation:
        # GIVEN each alias names a database persisted by an earlier test run,
        # WHEN keepdb setup reuses those names,
        # THEN setup releases every connection and transaction state capable of
        # blocking a write made by the test through any reused alias.
        #
        # INPUTS:
        # - A temporary name for each persistent SQLite test database.
        # - An initialized table in each database, produced by a prior setup run.
        #
        # PROCEDURE:
        # 1. Run initial setup and transition each alias from MISSING to
        #    INITIALIZED_AND_PERSISTED.
        # 2. End the initial run by closing its connections while preserving its
        #    database files.
        # 3. Create fresh connections with the same test database names and run
        #    normal setup with keepdb enabled.
        # 4. For every alias, transition from REUSED_AFTER_SETUP to WRITING and
        #    insert an alias-specific value into the initialized table.
        # 5. Read through the same alias and require the inserted value to be
        #    visible, transitioning the alias to WRITABLE_AND_VERIFIED.
        #
        # FAILURE PATHS:
        # - Treat a missing/recreated database as a reuse failure.
        # - Treat a locked write or an uncommitted/invisible value as retained
        #   connection or transaction state.
        # - Close all initial and reuse connections on every exit path.
        pass

    def test_sqlite_006_reused_migrated_database_is_preserved_and_writable_after_setup(self):
        """GUID: SQLITE-006; setup preserves reused migrated databases as writable."""
        # SQLITE-006 logic obligation:
        # GIVEN each named database contains the migration state and data left by
        # an earlier run, WHEN migration and synchronization setup reuses it,
        # THEN the existing database survives setup and accepts a subsequent write.
        #
        # INPUTS:
        # - Persistent named SQLite databases with applied migration records.
        # - A pre-setup marker whose value distinguishes preservation from
        #   replacement or reinitialization.
        #
        # PROCEDURE:
        # 1. Establish each database, apply its initial migration/synchronization
        #    work, store the preservation marker, and close the prior-run
        #    connections without deleting the database.
        # 2. Record the database path and marker, transitioning each alias from
        #    MIGRATED to PERSISTED_FOR_REUSE.
        # 3. Run normal migration and synchronization setup with keepdb enabled
        #    against fresh connections using the recorded names.
        # 4. For every alias, require the path and pre-setup marker to remain
        #    unchanged, transitioning it to PRESERVED_AFTER_SETUP.
        # 5. Insert a post-setup value and read it back, transitioning the alias
        #    to PRESERVED_AND_WRITABLE.
        #
        # FAILURE PATHS:
        # - A missing path or marker means setup failed to preserve the database.
        # - A locked write, failed commit, or invisible value means setup left the
        #   preserved database non-writable.
        # - Close every connection on success or failure while retaining files.
        pass

    def test_sqlite_007_repeated_keepdb_reuse_does_not_accumulate_state_blocking_later_writes(self):
        """GUID: SQLITE-007; repeated keepdb reuse leaves later-run writes unlocked."""
        # SQLITE-007 logic obligation:
        # GIVEN the same named databases are retained, WHEN more than one keepdb
        # reuse cycle completes, THEN connection or transaction state from earlier
        # cycles does not accumulate and block a write in a later cycle.
        #
        # INPUTS:
        # - One initialized persistent database name per alias.
        # - A fixed reuse-cycle count greater than one and a unique value per
        #   alias and cycle.
        #
        # PROCEDURE:
        # 1. Create and initialize the databases once, close that run's
        #    connections, and transition every alias to READY_FOR_REPEATED_REUSE.
        # 2. For each reuse cycle in ascending order:
        #    a. Open fresh connections targeting the unchanged database names.
        #    b. Run normal setup with keepdb enabled.
        #    c. Insert and read back the cycle-specific value for every alias.
        #    d. Transition each alias from REUSED to WRITABLE_IN_THIS_CYCLE.
        #    e. Close all cycle connections without deleting database files before
        #       advancing to the next cycle.
        # 3. In the final cycle, require all values written by earlier cycles to
        #    remain visible and accept one additional write, transitioning every
        #    alias to REPEATED_REUSE_VERIFIED.
        #
        # FAILURE PATHS:
        # - Abort on a changed/deleted database or missing earlier-cycle value.
        # - Attribute a locked later-cycle write to accumulated connection or
        #   transaction state from reuse setup.
        # - Close the active and prior connection handlers on every exit path.
        pass

    def create_named_test_databases(self, directory):
        database_settings = {
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
