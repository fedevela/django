from django.core import checks
from django.core.checks import Error, Warning
from django.db import models
from django.test import (
    SimpleTestCase, TestCase, override_settings, skipUnlessDBFeature,
)
from django.test.utils import (
    isolate_apps, modify_settings, override_system_checks,
)


class EmptyRouter:
    pass


@isolate_apps('check_framework', attr_name='apps')
@override_settings(DATABASE_ROUTERS=[])
@override_system_checks([checks.model_checks.check_all_models])
class DBTable001NoDatabaseRoutersContractTests(SimpleTestCase):
    """Verification obligations for GUID: DBTABLE-001."""

    def test_dbtable_001_duplicate_managed_table_without_routers_when_checked_reports_e028(self):
        class Model1(models.Model):
            class Meta:
                db_table = 'dbtable_001_general'

        class Model2(models.Model):
            class Meta:
                db_table = 'dbtable_001_general'

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "db_table 'dbtable_001_general' is used by multiple models: "
                "check_framework.Model1, check_framework.Model2.",
                obj='dbtable_001_general',
                id='models.E028',
            ),
        ])

    @modify_settings(INSTALLED_APPS={'append': 'basic'})
    @isolate_apps('basic', 'check_framework', kwarg_name='apps')
    def test_dbtable_001_duplicate_managed_table_across_apps_without_routers_when_checked_reports_e028(self, apps):
        class Model1(models.Model):
            class Meta:
                app_label = 'basic'
                db_table = 'dbtable_001_across_apps'

        class Model2(models.Model):
            class Meta:
                app_label = 'check_framework'
                db_table = 'dbtable_001_across_apps'

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [
            Error(
                "db_table 'dbtable_001_across_apps' is used by multiple models: "
                "basic.Model1, check_framework.Model2.",
                obj='dbtable_001_across_apps',
                id='models.E028',
            ),
        ])

    def test_dbtable_001_duplicate_managed_table_in_same_app_without_routers_when_checked_reports_e028(self):
        class Model1(models.Model):
            class Meta:
                db_table = 'dbtable_001_same_app'

        class Model2(models.Model):
            class Meta:
                db_table = 'dbtable_001_same_app'

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "db_table 'dbtable_001_same_app' is used by multiple models: "
                "check_framework.Model1, check_framework.Model2.",
                obj='dbtable_001_same_app',
                id='models.E028',
            ),
        ])


@isolate_apps('check_framework', attr_name='apps')
@override_settings(
    DATABASE_ROUTERS=['check_framework.test_model_checks.EmptyRouter'],
)
@override_system_checks([checks.model_checks.check_all_models])
class RoutedDuplicateDBTableContractTests(SimpleTestCase):
    """Verification obligations for GUIDs DBTABLE-002 through DBTABLE-004."""

    def run_same_app_check(self, table_name):
        class Model1(models.Model):
            class Meta:
                db_table = table_name

        class Model2(models.Model):
            class Meta:
                db_table = table_name

        return checks.run_checks(app_configs=self.apps.get_app_configs())

    def assert_routed_duplicate_warning(self, warning, db_table, model_labels):
        model_labels_str = ', '.join(model_labels)
        self.assertEqual(warning, Warning(
            "db_table '%s' is used by multiple models: %s."
            % (db_table, model_labels_str),
            hint=(
                'You have configured settings.DATABASE_ROUTERS. Verify that '
                '%s are correctly routed to separate databases.'
                % model_labels_str
            ),
            obj=db_table,
            id='models.W035',
        ))
        self.assertFalse(warning.is_serious())

    @modify_settings(INSTALLED_APPS={'append': 'basic'})
    @isolate_apps('basic', 'check_framework', kwarg_name='apps')
    def test_dbtable_002_routed_duplicate_managed_table_across_apps_reports_non_blocking_diagnostic_instead_of_e028(self, apps):
        class Model1(models.Model):
            class Meta:
                app_label = 'basic'
                db_table = 'dbtable_002_across_apps'

        class Model2(models.Model):
            class Meta:
                app_label = 'check_framework'
                db_table = 'dbtable_002_across_apps'

        warnings = checks.run_checks(app_configs=apps.get_app_configs())
        self.assertEqual(len(warnings), 1)
        self.assert_routed_duplicate_warning(
            warnings[0],
            'dbtable_002_across_apps',
            ['basic.Model1', 'check_framework.Model2'],
        )
        self.assertNotEqual(warnings[0].id, 'models.E028')

    def test_dbtable_003_routed_duplicate_managed_table_in_same_app_reports_non_blocking_diagnostic_instead_of_e028(self):
        warnings = self.run_same_app_check('dbtable_003_same_app')
        self.assertEqual(len(warnings), 1)
        self.assert_routed_duplicate_warning(
            warnings[0],
            'dbtable_003_same_app',
            ['check_framework.Model1', 'check_framework.Model2'],
        )
        self.assertNotEqual(warnings[0].id, 'models.E028')

    def test_dbtable_004_routed_duplicate_diagnostic_identifies_shared_table(self):
        warnings = self.run_same_app_check('dbtable_004_shared_table')
        self.assertEqual(warnings[0].obj, 'dbtable_004_shared_table')
        self.assertIn("db_table 'dbtable_004_shared_table'", warnings[0].msg)

    def test_dbtable_004_routed_duplicate_diagnostic_identifies_conflicting_models(self):
        warnings = self.run_same_app_check('dbtable_004_models')
        self.assertIn('check_framework.Model1', warnings[0].msg)
        self.assertIn('check_framework.Model2', warnings[0].msg)

    def test_dbtable_004_routed_duplicate_diagnostic_directs_user_to_verify_routing_separates_models(self):
        warnings = self.run_same_app_check('dbtable_004_routing_guidance')
        self.assertIn('Verify that', warnings[0].hint)
        self.assertIn('check_framework.Model1', warnings[0].hint)
        self.assertIn('check_framework.Model2', warnings[0].hint)
        self.assertIn('routed to separate databases', warnings[0].hint)


@isolate_apps('check_framework', attr_name='apps')
@override_system_checks([checks.model_checks.check_all_models])
class DuplicateDBTableTests(SimpleTestCase):
    def test_collision_in_same_app(self):
        class Model1(models.Model):
            class Meta:
                db_table = 'test_table'

        class Model2(models.Model):
            class Meta:
                db_table = 'test_table'

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "db_table 'test_table' is used by multiple models: "
                "check_framework.Model1, check_framework.Model2.",
                obj='test_table',
                id='models.E028',
            )
        ])

    @modify_settings(INSTALLED_APPS={'append': 'basic'})
    @isolate_apps('basic', 'check_framework', kwarg_name='apps')
    def test_collision_across_apps(self, apps):
        class Model1(models.Model):
            class Meta:
                app_label = 'basic'
                db_table = 'test_table'

        class Model2(models.Model):
            class Meta:
                app_label = 'check_framework'
                db_table = 'test_table'

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [
            Error(
                "db_table 'test_table' is used by multiple models: "
                "basic.Model1, check_framework.Model2.",
                obj='test_table',
                id='models.E028',
            )
        ])

    def test_no_collision_for_unmanaged_models(self):
        class Unmanaged(models.Model):
            class Meta:
                db_table = 'test_table'
                managed = False

        class Managed(models.Model):
            class Meta:
                db_table = 'test_table'

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_no_collision_for_proxy_models(self):
        class Model(models.Model):
            class Meta:
                db_table = 'test_table'

        class ProxyModel(Model):
            class Meta:
                proxy = True

        self.assertEqual(Model._meta.db_table, ProxyModel._meta.db_table)
        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])


@isolate_apps('check_framework', attr_name='apps')
@override_system_checks([checks.model_checks.check_all_models])
class IndexNameTests(SimpleTestCase):
    def test_collision_in_same_model(self):
        index = models.Index(fields=['id'], name='foo')

        class Model(models.Model):
            class Meta:
                indexes = [index, index]

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "index name 'foo' is not unique for model check_framework.Model.",
                id='models.E029',
            ),
        ])

    def test_collision_in_different_models(self):
        index = models.Index(fields=['id'], name='foo')

        class Model1(models.Model):
            class Meta:
                indexes = [index]

        class Model2(models.Model):
            class Meta:
                indexes = [index]

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "index name 'foo' is not unique amongst models: "
                "check_framework.Model1, check_framework.Model2.",
                id='models.E030',
            ),
        ])

    def test_collision_abstract_model(self):
        class AbstractModel(models.Model):
            class Meta:
                indexes = [models.Index(fields=['id'], name='foo')]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "index name 'foo' is not unique amongst models: "
                "check_framework.Model1, check_framework.Model2.",
                id='models.E030',
            ),
        ])

    def test_no_collision_abstract_model_interpolation(self):
        class AbstractModel(models.Model):
            name = models.CharField(max_length=20)

            class Meta:
                indexes = [models.Index(fields=['name'], name='%(app_label)s_%(class)s_foo')]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    @modify_settings(INSTALLED_APPS={'append': 'basic'})
    @isolate_apps('basic', 'check_framework', kwarg_name='apps')
    def test_collision_across_apps(self, apps):
        index = models.Index(fields=['id'], name='foo')

        class Model1(models.Model):
            class Meta:
                app_label = 'basic'
                indexes = [index]

        class Model2(models.Model):
            class Meta:
                app_label = 'check_framework'
                indexes = [index]

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [
            Error(
                "index name 'foo' is not unique amongst models: basic.Model1, "
                "check_framework.Model2.",
                id='models.E030',
            ),
        ])

    @modify_settings(INSTALLED_APPS={'append': 'basic'})
    @isolate_apps('basic', 'check_framework', kwarg_name='apps')
    def test_no_collision_across_apps_interpolation(self, apps):
        index = models.Index(fields=['id'], name='%(app_label)s_%(class)s_foo')

        class Model1(models.Model):
            class Meta:
                app_label = 'basic'
                constraints = [index]

        class Model2(models.Model):
            class Meta:
                app_label = 'check_framework'
                constraints = [index]

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [])


@isolate_apps('check_framework', attr_name='apps')
@override_system_checks([checks.model_checks.check_all_models])
@skipUnlessDBFeature('supports_table_check_constraints')
class ConstraintNameTests(TestCase):
    def test_collision_in_same_model(self):
        class Model(models.Model):
            class Meta:
                constraints = [
                    models.CheckConstraint(check=models.Q(id__gt=0), name='foo'),
                    models.CheckConstraint(check=models.Q(id__lt=100), name='foo'),
                ]

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "constraint name 'foo' is not unique for model "
                "check_framework.Model.",
                id='models.E031',
            ),
        ])

    def test_collision_in_different_models(self):
        constraint = models.CheckConstraint(check=models.Q(id__gt=0), name='foo')

        class Model1(models.Model):
            class Meta:
                constraints = [constraint]

        class Model2(models.Model):
            class Meta:
                constraints = [constraint]

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "constraint name 'foo' is not unique amongst models: "
                "check_framework.Model1, check_framework.Model2.",
                id='models.E032',
            ),
        ])

    def test_collision_abstract_model(self):
        class AbstractModel(models.Model):
            class Meta:
                constraints = [models.CheckConstraint(check=models.Q(id__gt=0), name='foo')]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "constraint name 'foo' is not unique amongst models: "
                "check_framework.Model1, check_framework.Model2.",
                id='models.E032',
            ),
        ])

    def test_no_collision_abstract_model_interpolation(self):
        class AbstractModel(models.Model):
            class Meta:
                constraints = [
                    models.CheckConstraint(check=models.Q(id__gt=0), name='%(app_label)s_%(class)s_foo'),
                ]
                abstract = True

        class Model1(AbstractModel):
            pass

        class Model2(AbstractModel):
            pass

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    @modify_settings(INSTALLED_APPS={'append': 'basic'})
    @isolate_apps('basic', 'check_framework', kwarg_name='apps')
    def test_collision_across_apps(self, apps):
        constraint = models.CheckConstraint(check=models.Q(id__gt=0), name='foo')

        class Model1(models.Model):
            class Meta:
                app_label = 'basic'
                constraints = [constraint]

        class Model2(models.Model):
            class Meta:
                app_label = 'check_framework'
                constraints = [constraint]

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [
            Error(
                "constraint name 'foo' is not unique amongst models: "
                "basic.Model1, check_framework.Model2.",
                id='models.E032',
            ),
        ])

    @modify_settings(INSTALLED_APPS={'append': 'basic'})
    @isolate_apps('basic', 'check_framework', kwarg_name='apps')
    def test_no_collision_across_apps_interpolation(self, apps):
        constraint = models.CheckConstraint(check=models.Q(id__gt=0), name='%(app_label)s_%(class)s_foo')

        class Model1(models.Model):
            class Meta:
                app_label = 'basic'
                constraints = [constraint]

        class Model2(models.Model):
            class Meta:
                app_label = 'check_framework'
                constraints = [constraint]

        self.assertEqual(checks.run_checks(app_configs=apps.get_app_configs()), [])
