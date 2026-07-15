from collections import Counter
from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from .models import Proxy, SharedCodenameProxyA, SharedCodenameProxyB, UserProxy
from .models.proxy import Concrete

update_proxy_permissions = import_module(
    'django.contrib.auth.migrations.0011_update_proxy_permissions'
)

G70_006_REQUIREMENT_TO_VERIFICATION = {
    "G70-006": [
        "G70_006UpdateProxyPermissionsTraceabilityTests::test_G70_006_unrelated_auth_permission_rows_preserve_identity_and_count_when_forward_migration_runs_for_proxy_models",
        "G70_006UpdateProxyPermissionsTraceabilityTests::test_G70_006_recorded_unrelated_tuple_counts_match_pre_migration_baseline_after_auth_0011_forward",
        "G70_006UpdateProxyPermissionsTraceabilityTests::test_G70_006_only_expected_proxy_permission_keys_transition_leaving_unrelated_rows_untouched",
    ],
}


class G70_006UpdateProxyPermissionsTraceabilityTests(TestCase):
    available_apps = [
        "auth_tests",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    def setUp(self):
        Permission.objects.all().delete()

    def test_G70_006_unrelated_auth_permission_rows_preserve_identity_and_count_when_forward_migration_runs_for_proxy_models(self):
        concrete_type = ContentType.objects.get_for_model(Concrete, for_concrete_model=True)
        proxy_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        user_concrete_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=True)
        user_proxy_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=False)
        shared_proxy_type = ContentType.objects.get_for_model(
            SharedCodenameProxyA,
            for_concrete_model=False,
        )
        shared_concrete_type = ContentType.objects.get_for_model(
            SharedCodenameProxyA,
            for_concrete_model=True,
        )

        unrelated_a = Permission.objects.create(
            content_type=concrete_type,
            codename="unrelated_non_proxy_permission",
            name="Non-proxy unrelated",
        )
        unrelated_b = Permission.objects.create(
            content_type=proxy_type,
            codename="unrelated_proxy_permission",
            name="Proxy unrelated",
        )
        unrelated_c = Permission.objects.create(
            content_type=user_concrete_type,
            codename="another_unrelated_user_proxy_source_permission",
            name="User proxy unrelated",
        )
        unrelated_d = Permission.objects.create(
            content_type=user_proxy_type,
            codename="unrelated_user_proxy_target_permission",
            name="User proxy unrelated target",
        )
        unrelated_e = Permission.objects.create(
            content_type=shared_proxy_type,
            codename="unrelated_shared_proxy_permission",
            name="Shared unrelated proxy",
        )
        unrelated_f = Permission.objects.create(
            content_type=shared_concrete_type,
            codename="unrelated_shared_proxy_source_permission",
            name="Shared unrelated proxy source",
        )

        Permission.objects.create(
            content_type=ContentType.objects.get_for_model(
                Proxy,
                for_concrete_model=True,
            ),
            codename="add_proxy",
            name="Legacy source permission",
        )

        baseline = {
            permission.pk: (
                permission.content_type_id,
                permission.codename,
                permission.name,
            )
            for permission in [unrelated_a, unrelated_b, unrelated_c, unrelated_d, unrelated_e, unrelated_f]
        }

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        post_migration = Permission.objects.filter(
            pk__in=baseline.keys()
        ).order_by("pk")

        self.assertEqual(len(post_migration), len(baseline))
        for permission in post_migration:
            self.assertEqual(
                (
                    permission.content_type_id,
                    permission.codename,
                    permission.name,
                ),
                baseline[permission.pk],
            )

    def test_G70_006_recorded_unrelated_tuple_counts_match_pre_migration_baseline_after_auth_0011_forward(self):
        # Unrelated tuple set includes proxy + non-proxy rows not in the migration key
        # domain for this test case.
        proxy_domain_model = (Proxy, SharedCodenameProxyB, UserProxy, SharedCodenameProxyA)
        for model in proxy_domain_model:
            for codename in (
                '%s_%s' % (action, model._meta.model_name)
                for action in model._meta.default_permissions
            ):
                Permission.objects.create(
                    content_type=ContentType.objects.get_for_model(
                        model,
                        for_concrete_model=False,
                    ),
                    codename=codename,
                    name="Domain baseline to be migrated",
                )

        unrelated_model = ContentType.objects.get_for_model(Concrete, for_concrete_model=True)
        Permission.objects.create(
            content_type=unrelated_model,
            codename="unrelated_domain_counter_1",
            name="Unrelated 1",
        )
        Permission.objects.create(
            content_type=unrelated_model,
            codename="unrelated_domain_counter_2",
            name="Unrelated 2",
        )
        Permission.objects.create(
            content_type=ContentType.objects.get_for_model(
                UserProxy,
                for_concrete_model=False,
            ),
            codename="shared_proxy_permission",
            name="Shared proxy row excluded from unrelated baseline",
        )

        baseline_counts = Counter(
            tuple(permission)
            for permission in Permission.objects.values_list(
                "content_type_id",
                "codename",
            )
            if tuple(permission) not in expected_domain
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        expected_domain = self._expected_permission_domain(proxy_domain_model)
        post_counts = Counter(
            tuple(permission)
            for permission in Permission.objects.values_list(
                "content_type_id",
                "codename",
            )
            if tuple(permission) not in expected_domain
        )

        self.assertEqual(post_counts, baseline_counts)
        self.assertEqual(len(post_counts), len(baseline_counts))

    def test_G70_006_only_expected_proxy_permission_keys_transition_leaving_unrelated_rows_untouched(self):
        proxy_models = (Proxy, SharedCodenameProxyA, SharedCodenameProxyB, UserProxy)
        expected_domain = self._expected_permission_domain(proxy_models)

        for model in proxy_models:
            concrete_type = ContentType.objects.get_for_model(
                model,
                for_concrete_model=True,
            )
            proxy_type = ContentType.objects.get_for_model(
                model,
                for_concrete_model=False,
            )
            for codename in self._required_permissions(model):
                Permission.objects.create(
                    content_type=concrete_type,
                    codename=codename,
                    name="Source before migration",
                )

        unrelated_rows = {
            (
                ContentType.objects.get_for_model(
                    SharedCodenameProxyA, for_concrete_model=False
                ).id,
                "another_unrelated",
            ): {
                "name": "Unrelated proxy model target",
            },
            (
                ContentType.objects.get_for_model(Concrete, for_concrete_model=True).id,
                "unrelated_non_proxy",
            ): {
                "name": "Unrelated non-proxy",
            },
            (
                ContentType.objects.get_for_model(UserProxy, for_concrete_model=True).id,
                "still_unrelated_non_migrated",
            ): {
                "name": "Unrelated non-proxy 2",
            },
        }
        for (content_type_id, codename), values in unrelated_rows.items():
            Permission.objects.create(
                content_type_id=content_type_id,
                codename=codename,
                name=values["name"],
            )

        pre_snapshot = {
            permission.id: (
                permission.content_type_id,
                permission.codename,
                permission.name,
            )
            for permission in Permission.objects.all()
            if (permission.content_type_id, permission.codename) not in expected_domain
        }

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        post_snapshot = {
            permission.id: (
                permission.content_type_id,
                permission.codename,
                permission.name,
            )
            for permission in Permission.objects.all()
            if (permission.content_type_id, permission.codename) not in expected_domain
        }

        self.assertEqual(post_snapshot, pre_snapshot)
        for model in proxy_models:
            proxy_type = ContentType.objects.get_for_model(
                model,
                for_concrete_model=False,
            )
            for codename in self._required_permissions(model):
                self.assertEqual(
                    Permission.objects.filter(
                        content_type=proxy_type,
                        codename=codename,
                    ).count(),
                    1,
                )

    def _required_permissions(self, model):
        return {
            "%s_%s" % (action, model._meta.model_name)
            for action in model._meta.default_permissions
        }.union(codename for codename, _name in model._meta.permissions)

    def _expected_permission_domain(self, models):
        domain = set()
        for model in models:
            concrete_type = ContentType.objects.get_for_model(
                model,
                for_concrete_model=True,
            )
            proxy_type = ContentType.objects.get_for_model(
                model,
                for_concrete_model=False,
            )
            for codename in self._required_permissions(model):
                domain.add((concrete_type.id, codename))
                domain.add((proxy_type.id, codename))
        return domain
