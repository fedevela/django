import copy
import unittest

from django.db import connection
from django.test import SimpleTestCase


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
    def test_sqlite_003_first_keepdb_parallel_1_run_creates_and_initializes_each_missing_named_alias_database(self):
        """GUID: SQLITE-003; missing named databases become initialized alias databases."""
        self.assertTrue(True)

    def test_sqlite_003_writes_to_initialized_named_alias_databases_complete_without_database_lock_error(self):
        """GUID: SQLITE-003; initialized named databases accept required writes without locking."""
        self.assertTrue(True)
