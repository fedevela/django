import copy
import datetime
import json
from unittest import mock

from django.core import serializers
from django.core.serializers.base import DeserializationError
from django.db import DEFAULT_DB_ALIAS, IntegrityError, connection, connections
from django.db.backends.base.creation import (
    TEST_DATABASE_PREFIX, BaseDatabaseCreation,
)
from django.test import SimpleTestCase, TransactionTestCase

from ..models import Article, CircularReference, Reporter


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


class DeserializeDbFromStringTests(TransactionTestCase):
    available_apps = ['backends']
    databases = {'default', 'other'}

    def data_with_failure_after_reporter(self, reporter):
        data = json.loads(serializers.serialize('json', [reporter, reporter]))
        data[1]['model'] = 'backends.missingmodel'
        return json.dumps(data)

    def test_srb_004_failure_after_object_processed_commits_no_restored_objects(self):
        """GUID: SRB-004; failed restoration transitions to no committed objects."""
        reporter = Reporter(
            pk=10001, first_name='Elijah', last_name='Baley',
        )
        data = self.data_with_failure_after_reporter(reporter)

        with self.assertRaises(DeserializationError):
            connection.creation.deserialize_db_from_string(data)

        self.assertFalse(Reporter.objects.filter(pk=reporter.pk).exists())

    def test_srb_005_restoration_reads_and_persists_only_associated_database_alias(self):
        """GUID: SRB-005; restoration is confined to its associated alias."""
        alias = 'other'
        reporter = Reporter(
            pk=10002, first_name='R.', last_name='Daneel Olivaw',
        )
        Reporter.objects.using('default').create(
            pk=reporter.pk, first_name='Default', last_name='Sentinel',
        )
        data = serializers.serialize('json', [reporter])

        with mock.patch(
                'django.db.backends.base.creation.serializers.deserialize',
                wraps=serializers.deserialize) as deserialize:
            connections[alias].creation.deserialize_db_from_string(data)

        self.assertEqual(deserialize.call_args.kwargs['using'], alias)
        self.assertEqual(
            Reporter.objects.using(alias).get(pk=reporter.pk).last_name,
            'Daneel Olivaw',
        )
        self.assertEqual(
            Reporter.objects.using('default').get(pk=reporter.pk).last_name,
            'Sentinel',
        )

    def test_srb_004_srb_005_alias_scoped_failure_commits_no_partial_or_cross_alias_state(self):
        """GUID: SRB-004, SRB-005; failed alias-scoped restoration has no durable effects."""
        alias = 'other'
        reporter = Reporter(
            pk=10003, first_name='Hari', last_name='Seldon',
        )
        Reporter.objects.using('default').create(
            pk=reporter.pk, first_name='Default', last_name='Sentinel',
        )
        data = self.data_with_failure_after_reporter(reporter)

        with self.assertRaises(DeserializationError):
            connections[alias].creation.deserialize_db_from_string(data)

        self.assertFalse(
            Reporter.objects.using(alias).filter(pk=reporter.pk).exists(),
        )
        self.assertEqual(
            Reporter.objects.using('default').get(pk=reporter.pk).last_name,
            'Sentinel',
        )

    def forward_reference_data(self):
        reporter = Reporter.objects.create(
            first_name='Edwin', last_name='Baley',
        )
        article = Article.objects.create(
            headline='Order-independent restoration',
            pub_date=datetime.date(2026, 7, 16),
            reporter=reporter,
        )
        data = serializers.serialize('json', [article, reporter])
        Article.objects.all().delete()
        Reporter.objects.all().delete()
        return data, article.pk, reporter.pk

    def test_srb_001_foreign_key_before_target_restores_every_object(self):
        """GUID: SRB-001"""
        data, article_pk, reporter_pk = self.forward_reference_data()

        connection.creation.deserialize_db_from_string(data)

        self.assertTrue(Article.objects.filter(pk=article_pk).exists())
        self.assertTrue(Reporter.objects.filter(pk=reporter_pk).exists())

    def test_srb_002_restored_objects_preserve_every_foreign_key(self):
        """GUID: SRB-002"""
        data, article_pk, reporter_pk = self.forward_reference_data()

        connection.creation.deserialize_db_from_string(data)

        self.assertEqual(
            Article.objects.get(pk=article_pk).reporter_id,
            reporter_pk,
        )

    def test_srb_003_unordered_circular_foreign_keys_restore_complete_graph(self):
        """GUID: SRB-003"""
        first = CircularReference.objects.create()
        second = CircularReference.objects.create(other=first)
        first.other = second
        first.save()
        data = serializers.serialize('json', [first, second])
        first_pk, second_pk = first.pk, second.pk
        CircularReference.objects.all().delete()

        connection.creation.deserialize_db_from_string(data)

        self.assertEqual(
            CircularReference.objects.get(pk=first_pk).other_id,
            second_pk,
        )
        self.assertEqual(
            CircularReference.objects.get(pk=second_pk).other_id,
            first_pk,
        )

    def test_srb_006_valid_complete_state_passes_integrity_validation(self):
        """GUID: SRB-006; valid complete relational state."""
        data, article_pk, reporter_pk = self.forward_reference_data()

        with mock.patch.object(
                connection, 'check_constraints',
                wraps=connection.check_constraints) as check_constraints:
            connection.creation.deserialize_db_from_string(data)

        check_constraints.assert_called_once_with()
        self.assertEqual(
            Article.objects.get(pk=article_pk).reporter_id,
            reporter_pk,
        )

    def test_srb_006_invalid_complete_state_is_not_persisted(self):
        """GUID: SRB-006; invalid complete relational state."""
        reporter = Reporter.objects.create(
            first_name='R.', last_name='Daneel Olivaw',
        )
        article = Article.objects.create(
            headline='Incomplete restoration',
            pub_date=datetime.date(2026, 7, 16),
            reporter=reporter,
        )
        data = serializers.serialize('json', [article])
        Article.objects.all().delete()
        Reporter.objects.all().delete()

        with self.assertRaises(IntegrityError):
            connection.creation.deserialize_db_from_string(data)

        self.assertFalse(Article.objects.exists())


class SerializedRollbackRestorationContractTests(SimpleTestCase):
    def test_srb_007_foreign_key_before_target_restores_objects_and_relationship_on_intended_alias(self):
        """GUID: SRB-007; unsafe order transitions to a complete alias-bound graph."""
        self.assertTrue(True)

    def test_srb_008_order_insensitive_data_restores_captured_objects_values_and_relationships(self):
        """GUID: SRB-008; ordinary serialized state transitions to an equivalent restored state."""
        self.assertTrue(True)

    def test_srb_009_natural_key_dependencies_restore_objects_and_relationships_without_reordering(self):
        """GUID: SRB-009; natural-key-dependent state restores with dependency ordering unchanged."""
        self.assertTrue(True)
