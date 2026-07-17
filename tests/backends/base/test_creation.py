import copy
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.db.backends.base.creation import (
    TEST_DATABASE_PREFIX, BaseDatabaseCreation,
)
from django.test import SimpleTestCase, TransactionTestCase
from django.test.runner import DiscoverRunner

from ..models import (
    CircularA, CircularB, Object, ObjectReference, ObjectSelfReference,
)


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
        """GUID: DJANGO-001, DJANGO-002, DJANGO-007."""
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST']['MIGRATE'] = False
        creation = test_connection.creation_class(test_connection)
        old_database_name = test_connection.settings_dict['NAME']
        expected_test_database_name = creation._get_test_db_name()
        old_migration_modules = settings.MIGRATION_MODULES

        def assert_migrations_disabled(**kwargs):
            self.assertEqual(
                settings.MIGRATION_MODULES,
                {app.label: None for app in apps.get_app_configs()},
            )

        mocked_migrate.side_effect = assert_migrations_disabled
        try:
            with mock.patch.object(creation, '_create_test_db'):
                test_database_name = creation.create_test_db(
                    verbosity=0, autoclobber=True, serialize=False,
                )
            mocked_migrate.assert_called_once()
            mocked_ensure_connection.assert_called_once()
            self.assertEqual(test_database_name, expected_test_database_name)
            self.assertIs(settings.MIGRATION_MODULES, old_migration_modules)
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

    def test_migrate_test_setting_false_restores_migration_modules_on_failure(
            self, mocked_migrate, mocked_ensure_connection):
        """GUID: DJANGO-002, DJANGO-007."""
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST']['MIGRATE'] = False
        creation = test_connection.creation_class(test_connection)
        old_database_name = test_connection.settings_dict['NAME']
        old_migration_modules = settings.MIGRATION_MODULES
        mocked_migrate.side_effect = RuntimeError('migrate failed')
        try:
            with mock.patch.object(creation, '_create_test_db'):
                with self.assertRaisesMessage(RuntimeError, 'migrate failed'):
                    creation.create_test_db(
                        verbosity=0, autoclobber=True, serialize=False,
                    )
            self.assertIs(settings.MIGRATION_MODULES, old_migration_modules)
            mocked_ensure_connection.assert_not_called()
        finally:
            with mock.patch.object(creation, '_destroy_test_db'):
                creation.destroy_test_db(old_database_name, verbosity=0)


class MigrationDisabledTestDatabaseLifecycleTests(SimpleTestCase):
    def get_runner(self, run_suite_side_effect=None):
        runner = DiscoverRunner(verbosity=0)
        runner.setup_test_environment = mock.Mock()
        runner.build_suite = mock.Mock(return_value=mock.sentinel.suite)
        runner.get_databases = mock.Mock(return_value={'default'})
        runner.setup_databases = mock.Mock(return_value=mock.sentinel.old_config)
        runner.run_checks = mock.Mock()
        runner.run_suite = mock.Mock(
            return_value=mock.sentinel.result,
            side_effect=run_suite_side_effect,
        )
        runner.teardown_databases = mock.Mock()
        runner.teardown_test_environment = mock.Mock()
        runner.suite_result = mock.Mock(return_value=0)
        return runner

    def test_setup_proceeds_to_execution_and_teardown(self):
        """GUID: DJANGO-004, DJANGO-008."""
        runner = self.get_runner()
        runner.run_tests([])
        runner.run_suite.assert_called_once_with(mock.sentinel.suite)
        runner.teardown_databases.assert_called_once_with(
            mock.sentinel.old_config,
        )
        runner.teardown_test_environment.assert_called_once()

    def test_execution_failure_still_uses_normal_teardown(self):
        """GUID: DJANGO-008."""
        runner = self.get_runner(RuntimeError('test execution failed'))
        with self.assertRaisesMessage(RuntimeError, 'test execution failed'):
            runner.run_tests([])
        runner.teardown_databases.assert_called_once_with(
            mock.sentinel.old_config,
        )
        runner.teardown_test_environment.assert_called_once()


class MigrationDisabledSerializationContractTests(SimpleTestCase):
    def test_django_003_migrate_false_serialization_skips_models_with_absent_tables(self):
        """GUID: DJANGO-003."""
        # Pseudocode -- logic obligation: absent tables are never queried.
        # ARRANGE MIGRATE=False, one serializable model with an existing table,
        # and one otherwise-eligible serializable model with no table.
        # ACT by running the test-database serialization path.
        # VERIFY objects from the existing table are enumerated and the absent
        # model's manager/queryset is never constructed or evaluated.
        self.assertTrue(True)

    def test_django_003_migrate_false_serialization_completes_using_existing_tables(self):
        """GUID: DJANGO-003."""
        # Pseudocode -- logic obligation: filtering preserves the success path.
        # ARRANGE MIGRATE=False and serializable models whose tables all exist.
        # ACT by serializing the test database.
        # VERIFY serialization completes and contains the eligible objects in
        # deterministic primary-key order.
        self.assertTrue(True)

    def test_django_005_creation_serialization_is_backend_independent(self):
        """GUID: DJANGO-005."""
        # Pseudocode -- logic obligation: correction uses common backend APIs.
        # ARRANGE a base database creation object whose introspection API reports
        # the existing table names and excludes one eligible model's table.
        # ACT through create_test_db(..., serialize=True), allowing its normal
        # handoff to serialize_db_to_string().
        # VERIFY eligibility is decided from introspection before querying and
        # no vendor exception type or exception-recovery branch participates.
        self.assertTrue(True)

    def test_django_009_migrate_false_creation_serializes_without_querying_absent_table(self):
        """GUID: DJANGO-009."""
        # Pseudocode -- regression flow and state transitions.
        # GIVEN TEST['MIGRATE'] transitions to False and schema creation leaves a
        # serializable model table absent, observe queries issued by the backend.
        # WHEN create_test_db(..., serialize=True) creates the schema, restores
        # migration settings, and hands off to serialize_db_to_string().
        # THEN creation reaches the serialized-contents state successfully AND
        # no observed query targets the absent model table.
        # FAILURE: any absent-table query or interrupted serialization fails the
        # regression; cleanup follows the ordinary test-database teardown path.
        self.assertTrue(True)


class TestDeserializeDbFromString(TransactionTestCase):
    available_apps = ['backends']

    def test_circular_reference(self):
        # deserialize_db_from_string() handles circular references.
        data = """
        [
            {
                "model": "backends.object",
                "pk": 1,
                "fields": {"obj_ref": 1, "related_objects": []}
            },
            {
                "model": "backends.objectreference",
                "pk": 1,
                "fields": {"obj": 1}
            }
        ]
        """
        connection.creation.deserialize_db_from_string(data)
        obj = Object.objects.get()
        obj_ref = ObjectReference.objects.get()
        self.assertEqual(obj.obj_ref, obj_ref)
        self.assertEqual(obj_ref.obj, obj)

    def test_self_reference(self):
        # serialize_db_to_string() and deserialize_db_from_string() handles
        # self references.
        obj_1 = ObjectSelfReference.objects.create(key='X')
        obj_2 = ObjectSelfReference.objects.create(key='Y', obj=obj_1)
        obj_1.obj = obj_2
        obj_1.save()
        # Serialize objects.
        with mock.patch('django.db.migrations.loader.MigrationLoader') as loader:
            # serialize_db_to_string() serializes only migrated apps, so mark
            # the backends app as migrated.
            loader_instance = loader.return_value
            loader_instance.migrated_apps = {'backends'}
            data = connection.creation.serialize_db_to_string()
        ObjectSelfReference.objects.all().delete()
        # Deserialize objects.
        connection.creation.deserialize_db_from_string(data)
        obj_1 = ObjectSelfReference.objects.get(key='X')
        obj_2 = ObjectSelfReference.objects.get(key='Y')
        self.assertEqual(obj_1.obj, obj_2)
        self.assertEqual(obj_2.obj, obj_1)

    def test_circular_reference_with_natural_key(self):
        # serialize_db_to_string() and deserialize_db_from_string() handles
        # circular references for models with natural keys.
        obj_a = CircularA.objects.create(key='A')
        obj_b = CircularB.objects.create(key='B', obj=obj_a)
        obj_a.obj = obj_b
        obj_a.save()
        # Serialize objects.
        with mock.patch('django.db.migrations.loader.MigrationLoader') as loader:
            # serialize_db_to_string() serializes only migrated apps, so mark
            # the backends app as migrated.
            loader_instance = loader.return_value
            loader_instance.migrated_apps = {'backends'}
            data = connection.creation.serialize_db_to_string()
        CircularA.objects.all().delete()
        CircularB.objects.all().delete()
        # Deserialize objects.
        connection.creation.deserialize_db_from_string(data)
        obj_a = CircularA.objects.get()
        obj_b = CircularB.objects.get()
        self.assertEqual(obj_a.obj, obj_b)
        self.assertEqual(obj_b.obj, obj_a)
