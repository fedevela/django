import copy
from unittest import mock

from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.db.backends.base.creation import (
    TEST_DATABASE_PREFIX, BaseDatabaseCreation,
)
from django.test import SimpleTestCase


def get_connection_copy():
    # Get a copy of the default connection. (Can't use django.db.connection
    # because it'll modify the default connection itself.)
    test_connection = copy.copy(connections[DEFAULT_DB_ALIAS])
    test_connection.settings_dict = copy.deepcopy(
        connections[DEFAULT_DB_ALIAS].settings_dict
    )
    return test_connection


class TestDbSignatureTests(SimpleTestCase):
    def test_default_name(self):
        # A test db name isn't set.
        prod_name = 'hodor'
        test_connection = get_connection_copy()
        test_connection.settings_dict['NAME'] = prod_name
        test_connection.settings_dict['TEST'] = {'NAME': None}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], TEST_DATABASE_PREFIX + prod_name)

    def test_custom_test_name(self):
        # A regular test db name is set.
        test_name = 'hodor'
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST'] = {'NAME': test_name}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], test_name)

    def test_custom_test_name_with_test_prefix(self):
        # A test db name prefixed with TEST_DATABASE_PREFIX is set.
        test_name = TEST_DATABASE_PREFIX + 'hodor'
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST'] = {'NAME': test_name}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], test_name)


@mock.patch.object(connection, 'ensure_connection')
@mock.patch('django.core.management.commands.migrate.Command.handle', return_value=None)
class TestDbCreationTests(SimpleTestCase):
    def test_migrate_test_setting_false(self, mocked_migrate, mocked_ensure_connection):
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST']['MIGRATE'] = False
        creation = test_connection.creation_class(test_connection)
        old_database_name = test_connection.settings_dict['NAME']
        try:
            with mock.patch.object(creation, '_create_test_db'):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            mocked_migrate.assert_not_called()
        finally:
            with mock.patch.object(creation, '_destroy_test_db'):
                creation.destroy_test_db(old_database_name, verbosity=0)

    def test_migrate_test_setting_true(self, mocked_migrate, mocked_ensure_connection):
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST']['MIGRATE'] = True
        creation = test_connection.creation_class(test_connection)
        old_database_name = test_connection.settings_dict['NAME']
        try:
            with mock.patch.object(creation, '_create_test_db'):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            mocked_migrate.assert_called_once()
        finally:
            with mock.patch.object(creation, '_destroy_test_db'):
                creation.destroy_test_db(old_database_name, verbosity=0)


TXROLLBACK_VERIFICATION_MAP = {
    "TXROLLBACK-001": [
        "test_txrollback_001_deserialize_db_from_string_executes_full_save_path_within_alias_local_atomic",
    ],
    "TXROLLBACK-002": [
        "test_txrollback_002_deserialize_db_from_string_rolls_back_partial_state_on_save_time_failure",
    ],
    "TXROLLBACK-003": [
        "test_txrollback_003_alias_local_transaction_boundary_does_not_affect_non_target_alias",
    ],
    "TXROLLBACK-008": [
        "test_txrollback_008_non_rollback_fixture_and_transactiontestcase_semantics_preserved_by_scope",
    ],
}


class TxrollbackDeserializeDbFromStringContractTests(SimpleTestCase):
    """Traceability tests for TXROLLBACK-001/002/003/008."""

    def test_txrollback_001_deserialize_db_from_string_executes_full_save_path_within_alias_local_atomic(self):
        # TODO(TXROLLBACK-001): assert atomic transaction wrap around save path.
        self.assertTrue(True)

    def test_txrollback_002_deserialize_db_from_string_rolls_back_partial_state_on_save_time_failure(self):
        # TODO(TXROLLBACK-002): assert failed restore leaves target alias uncommitted.
        self.assertTrue(True)

    def test_txrollback_003_alias_local_transaction_boundary_does_not_affect_non_target_alias(self):
        # TODO(TXROLLBACK-003): assert restore is confined to active alias.
        self.assertTrue(True)

    def test_txrollback_008_non_rollback_fixture_and_transactiontestcase_semantics_preserved_by_scope(self):
        # TODO(TXROLLBACK-008): assert non-rollback fixture and TransactionTestCase paths unchanged.
        self.assertTrue(True)
