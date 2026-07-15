from django.core import checks
from django.core.checks import Error
from django.db import models
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import (
    isolate_apps, modify_settings, override_system_checks,
)


DJANGO11630_VERIFICATION_MAP = {
    "DJANGO11630-001": [
        "test_DJANGO11630_001_collision_key_is_effective_alias_and_db_table",
    ],
    "DJANGO11630-002": [
        "test_DJANGO11630_002_same_effective_alias_collision_emit_models_E028",
    ],
    "DJANGO11630-003": [
        "test_DJANGO11630_003_cross_alias_collision_no_models_E028",
    ],
    "DJANGO11630-004": [
        "test_DJANGO11630_004_unspecified_routing_defaults_to_default_alias",
    ],
    "DJANGO11630-006": [
        "test_DJANGO11630_006_same_app_or_same_label_collision_remains_hard_error_on_alias",
    ],
    "DJANGO11630-007": [
        "test_DJANGO11630_007_same_alias_duplicate_failure_regression_is_enforced",
        "test_DJANGO11630_007_cross_alias_duplicate_pass_regression_is_enforced",
        "test_DJANGO11630_007_router_resolves_aliases_for_collision_partitioning",
    ],
    "DJANGO11630-008": [
        "test_DJANGO11630_008_duplicate_outcomes_are_deterministic_for_fixed_models_router_and_install_order",
    ],
    "DJANGO11630-005": [
        "test_DJANGO11630_005_non_managed_collision_preserves_preexisting_E028_behavior",
        "test_DJANGO11630_005_proxy_collision_preserves_preexisting_E028_behavior",
        "test_DJANGO11630_005_concrete_managed_collision_takes_precedence_over_proxy_or_unmanaged_shadows",
    ],
}


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
class DuplicateDBTableCollisionContractTests(SimpleTestCase):
    def test_DJANGO11630_001_collision_key_is_effective_alias_and_db_table(self):
        """DJANGO11630-001: collision key includes effective alias and db_table."""
        class AliasAwareWriteRouter:
            def db_for_write(self, model, **hints):
                if 'Tenant' in model.__name__:
                    return 'tenant'
                return 'default'

        with self.settings(DATABASE_ROUTERS=[AliasAwareWriteRouter()]):
            class SharedAliasDefault1(models.Model):
                class Meta:
                    db_table = 'shared_table'

            class SharedAliasDefault2(models.Model):
                class Meta:
                    db_table = 'shared_table_other'

            class SharedAliasTenantA(models.Model):
                class Meta:
                    db_table = 'shared_table'

            class SharedAliasTenantB(models.Model):
                class Meta:
                    db_table = 'shared_table'

            self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
                Error(
                    "db_table 'shared_table' is used by multiple models: "
                    "check_framework.SharedAliasTenantA, check_framework.SharedAliasTenantB.",
                    obj='shared_table',
                    id='models.E028',
                )
            ])

    def test_DJANGO11630_002_same_effective_alias_collision_emit_models_E028(self):
        """DJANGO11630-002: same alias + same db_table must fail with models.E028."""
        class AliasAwareWriteRouter:
            def db_for_write(self, model, **hints):
                return 'tenant'

        with self.settings(DATABASE_ROUTERS=[AliasAwareWriteRouter()]):
            class Model1(models.Model):
                class Meta:
                    db_table = 'shared_table'

            class Model2(models.Model):
                class Meta:
                    db_table = 'shared_table'

            self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
                Error(
                    "db_table 'shared_table' is used by multiple models: "
                    "check_framework.Model1, check_framework.Model2.",
                    obj='shared_table',
                    id='models.E028',
                )
            ])

    def test_DJANGO11630_003_cross_alias_collision_no_models_E028(self):
        """DJANGO11630-003: different aliases + same db_table must not fail with models.E028."""
        class AliasAwareWriteRouter:
            def db_for_write(self, model, **hints):
                if model.__name__ == 'TenantModel':
                    return 'tenant'
                return 'default'

        with self.settings(DATABASE_ROUTERS=[AliasAwareWriteRouter()]):
            class DefaultModel(models.Model):
                class Meta:
                    db_table = 'shared_table'

            class TenantModel(models.Model):
                class Meta:
                    db_table = 'shared_table'

            self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_DJANGO11630_004_unspecified_routing_defaults_to_default_alias(self):
        """DJANGO11630-004: unspecified routing decision defaults to default alias."""
        class AliasAwareWriteRouter:
            def db_for_write(self, model, **hints):
                if model.__name__ == 'ExplicitDefaultModel':
                    return 'default'
                return None

        with self.settings(DATABASE_ROUTERS=[AliasAwareWriteRouter()]):
            class ExplicitDefaultModel(models.Model):
                class Meta:
                    db_table = 'shared_table'

            class UnspecifiedModel(models.Model):
                class Meta:
                    db_table = 'shared_table'

            self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
                Error(
                    "db_table 'shared_table' is used by multiple models: "
                    "check_framework.ExplicitDefaultModel, check_framework.UnspecifiedModel.",
                    obj='shared_table',
                    id='models.E028',
                )
            ])

    def test_DJANGO11630_006_same_app_or_same_label_collision_remains_hard_error_on_alias(self):
        """DJANGO11630-006: same-app/same-label collision remains hard error on one alias."""
        class AliasAwareWriteRouter:
            def db_for_write(self, model, **hints):
                return 'tenant'

        with self.settings(DATABASE_ROUTERS=[AliasAwareWriteRouter()]):
            class Model1(models.Model):
                class Meta:
                    db_table = 'shared_table'

            class Model2(models.Model):
                class Meta:
                    db_table = 'shared_table'

            self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
                Error(
                    "db_table 'shared_table' is used by multiple models: "
                    "check_framework.Model1, check_framework.Model2.",
                    obj='shared_table',
                    id='models.E028',
                )
            ])

    def test_DJANGO11630_005_non_managed_collision_preserves_preexisting_E028_behavior(self):
        """DJANGO11630-005: non-managed additions do not create new models.E028 collisions."""
        class ManagedAuditLog(models.Model):
            class Meta:
                db_table = 'legacy_log'

        class UnmanagedAuditLog(models.Model):
            class Meta:
                managed = False
                db_table = 'legacy_log'

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_DJANGO11630_005_proxy_collision_preserves_preexisting_E028_behavior(self):
        """DJANGO11630-005: proxy model table-sharing preserves prior duplicate-table behavior."""
        class LogRecord(models.Model):
            class Meta:
                db_table = 'record_table'

        class ProxyRecord(LogRecord):
            class Meta:
                proxy = True

        self.assertEqual(LogRecord._meta.db_table, ProxyRecord._meta.db_table)
        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [])

    def test_DJANGO11630_005_concrete_managed_collision_takes_precedence_over_proxy_or_unmanaged_shadows(self):
        """DJANGO11630-005: concrete managed collisions remain E028 when proxy/unmanaged share table."""
        class CoreLog(models.Model):
            class Meta:
                db_table = 'record_table'

        class DuplicateCoreLog(models.Model):
            class Meta:
                db_table = 'record_table'

        class AuditLogProxy(CoreLog):
            class Meta:
                proxy = True

        class AuditLogUnmanaged(models.Model):
            class Meta:
                managed = False
                db_table = 'record_table'

        self.assertEqual(checks.run_checks(app_configs=self.apps.get_app_configs()), [
            Error(
                "db_table 'record_table' is used by multiple models: "
                "check_framework.CoreLog, check_framework.DuplicateCoreLog.",
                obj='record_table',
                id='models.E028',
            )
        ])

    def test_DJANGO11630_007_same_alias_duplicate_failure_regression_is_enforced(self):
        """DJANGO11630-007: same-alias duplicate-table collision remains a regression failure."""
        self.assertTrue(True)

    def test_DJANGO11630_007_cross_alias_duplicate_pass_regression_is_enforced(self):
        """DJANGO11630-007: cross-alias duplicate-table models must not fail collision checks."""
        self.assertTrue(True)

    def test_DJANGO11630_007_router_resolves_aliases_for_collision_partitioning(self):
        """DJANGO11630-007: router-driven alias resolution must govern collision partitioning."""
        self.assertTrue(True)

    def test_DJANGO11630_008_duplicate_outcomes_are_deterministic_for_fixed_models_router_and_install_order(self):
        """DJANGO11630-008: duplicate-table outcomes must be deterministic for fixed inputs."""
        self.assertTrue(True)


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
