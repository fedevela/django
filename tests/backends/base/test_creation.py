import json
import copy
from unittest import mock

from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.db.backends.base.creation import (
    TEST_DATABASE_PREFIX, BaseDatabaseCreation,
)
from django.test import SimpleTestCase, TransactionTestCase


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


TXROLLBACK_ARCHITECTURE_MAP = {
    "TXROLLBACK-001": {
        "pressure": "Ownership + atomicity boundary",
        "owner": "BaseDatabaseCreation",
        "locus": "django/db/backends/base/creation.py:BaseDatabaseCreation.deserialize_db_from_string",
        "contract": "deserialize_db_from_string(self, data) wraps deserialize+save path in one atomic block using the active alias",
        "invariants": [
            "all obj.save() calls execute within one alias-local transaction boundary",
            "control flow stays unchanged for call signature and return semantics",
        ],
    },
    "TXROLLBACK-002": {
        "pressure": "Failure isolation",
        "owner": "BaseDatabaseCreation.deserialize_db_from_string",
        "locus": "django/db/backends/base/creation.py:deserialize_db_from_string",
        "contract": "any exception during deserialize/save propagates and leaves the active alias transaction rolled back",
        "boundary": "rollback scope is limited to self.connection.alias only",
        "invariants": [
            "no partial rows committed for the target alias when save-time exceptions occur",
            "pre-restore state remains observable after failure",
        ],
    },
    "TXROLLBACK-003": {
        "pressure": "Dependency direction / alias isolation",
        "owner": "BaseDatabaseCreation + TransactionTestCase._fixture_setup",
        "locus": (
            "django/db/backends/base/creation.py:deserialize_db_from_string",
            "django/test/testcases.py:_fixture_setup",
        ),
        "contract": "transaction.atomic(using=self.connection.alias) prevents cross-alias transaction coupling",
        "boundary": "method only touches db_name resolved from self.connection.alias",
        "invariants": [
            "parallel aliases (e.g. default/replica) are unaffected by restore action",
            "other aliases continue using their own fixture setup/transactions",
        ],
    },
    "TXROLLBACK-008": {
        "pressure": "Compatibility seam preservation",
        "owner": "Fixture loading stack",
        "locus": [
            "django/test/testcases.py:_fixture_setup",
            "django/core/management/commands/loaddata.py",
            "django/db/backends/base/creation.py:deserialize_db_from_string",
        ],
        "contract": "atomicity is introduced only in deserialize_db_from_string, while loaddata path and existing TransactionTestCase semantics remain structurally unchanged",
        "invariants": [
            "deserialize_db_from_string behavior is the only changed restore operation",
            "fixtures path in _fixture_setup retains original order and call points",
            "serialized_rollback gating remains the same",
        ],
    },
}


class TxrollbackDeserializeDbFromStringContractTests(TransactionTestCase):
    """Traceability tests for TXROLLBACK-001/002/003/008."""

    def test_txrollback_001_deserialize_db_from_string_executes_full_save_path_within_alias_local_atomic(self):
        db_connection = connections[DEFAULT_DB_ALIAS]
        creation = db_connection.creation_class(db_connection)
        save_depth = {"depth": 0}
        save_events = []
        atomic_calls = []

        class TrackingAtomic:
            def __init__(self, *args, **kwargs):
                atomic_calls.append((args, kwargs))

            def __enter__(self):
                save_depth["depth"] += 1
                return self

            def __exit__(self, exc_type, exc, tb):
                save_depth["depth"] -= 1
                return False

        class TrackingObject:
            def __init__(self, value):
                self.value = value

            def save(self):
                save_events.append((self.value, save_depth["depth"]))

        with mock.patch(
            "django.db.backends.base.creation.serializers.deserialize",
            return_value=[TrackingObject(1), TrackingObject(2)],
        ), mock.patch("django.db.backends.base.creation.transaction.atomic", TrackingAtomic):
            creation.deserialize_db_from_string("[]")

        self.assertEqual(atomic_calls, [((), {"using": db_connection.alias})])
        self.assertEqual(save_events, [(1, 1), (2, 1)])
        self.assertEqual(save_depth["depth"], 0)

    def test_txrollback_002_deserialize_db_from_string_rolls_back_partial_state_on_save_time_failure(self):
        db_connection = connections[DEFAULT_DB_ALIAS]
        creation = db_connection.creation_class(db_connection)
        payload = json.dumps([
            {"model": "auth.group", "fields": {"name": "txrollback-rollback"}},
            {"model": "auth.group", "fields": {"name": "txrollback-rollback"}},
        ])
        pre_count = Group.objects.filter(name="txrollback-rollback").count()

        with self.assertRaises(IntegrityError):
            creation.deserialize_db_from_string(payload)

        self.assertEqual(
            pre_count,
            Group.objects.filter(name="txrollback-rollback").count(),
        )

    def test_txrollback_003_alias_local_transaction_boundary_does_not_affect_non_target_alias(self):
        db_connection = connections[DEFAULT_DB_ALIAS]
        creation = db_connection.creation_class(db_connection)
        atomic_calls = []

        class TrackingAtomic:
            def __init__(self, *args, **kwargs):
                atomic_calls.append(kwargs["using"])

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch(
            "django.db.backends.base.creation.serializers.deserialize",
            return_value=[],
        ), mock.patch("django.db.backends.base.creation.transaction.atomic", TrackingAtomic):
            creation.deserialize_db_from_string("[]")

        self.assertEqual(atomic_calls, [db_connection.alias])

    def test_txrollback_008_non_rollback_fixture_and_transactiontestcase_semantics_preserved_by_scope(self):
        class NonRollbackFixtureCase(TransactionTestCase):
            available_apps = ["auth"]
            databases = {"default"}
            fixtures = ["should_not_be_loaded.json"]
            serialized_rollback = False

        with mock.patch("django.test.testcases.call_command") as call_command, mock.patch(
            "django.db.backends.base.creation.BaseDatabaseCreation.deserialize_db_from_string",
            return_value=None,
        ) as deserialize_db_from_string:
            test_case = NonRollbackFixtureCase()
            test_case._fixture_setup()
            call_command.assert_called_once_with(
                "loaddata",
                "should_not_be_loaded.json",
                verbosity=0,
                database="default",
            )
            deserialize_db_from_string.assert_not_called()
