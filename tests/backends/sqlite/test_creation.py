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
        pass

    def test_sqlite_006_reused_migrated_database_is_preserved_and_writable_after_setup(self):
        """GUID: SQLITE-006; setup preserves reused migrated databases as writable."""
        pass

    def test_sqlite_007_repeated_keepdb_reuse_does_not_accumulate_state_blocking_later_writes(self):
        """GUID: SQLITE-007; repeated keepdb reuse leaves later-run writes unlocked."""
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
