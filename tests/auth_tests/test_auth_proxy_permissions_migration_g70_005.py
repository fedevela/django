from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from .models import SharedCodenameProxyA, SharedCodenameProxyB
from tests.contenttypes_tests.models import SharedCodenameProxy as CrossAppSharedCodenameProxy


update_proxy_permissions = import_module(
    'django.contrib.auth.migrations.0011_update_proxy_permissions'
)


SHARED_CODENAME = 'shared_proxy_permission'


G70_005_REQUIREMENT_TO_VERIFICATION = {
    "G70-005": [
        "G70_005UpdateProxyPermissionsTraceabilityTests::test_G70_005_scope_proxy_permission_updates_by_resolved_content_type_and_codename",
        "G70_005UpdateProxyPermissionsTraceabilityTests::test_G70_005_keep_same_app_label_proxy_models_isolated_by_content_type_and_codename",
        "G70_005UpdateProxyPermissionsTraceabilityTests::test_G70_005_keep_different_app_label_proxy_models_isolated_by_content_type_and_codename",
        "G70_005UpdateProxyPermissionsTraceabilityTests::test_G70_005_prevent_cross_pollution_for_same_codename_across_content_types",
    ],
}


class G70_005UpdateProxyPermissionsTraceabilityTests(TestCase):
    available_apps = [
        "auth_tests",
        "contenttypes_tests",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    def setUp(self):
        Permission.objects.all().delete()

    def _concrete_type(self, model):
        return ContentType.objects.get_for_model(model, for_concrete_model=True)

    def _proxy_type(self, model):
        return ContentType.objects.get_for_model(model, for_concrete_model=False)

    def test_G70_005_scope_proxy_permission_updates_by_resolved_content_type_and_codename(self):
        concrete_a = self._concrete_type(SharedCodenameProxyA)
        proxy_a = self._proxy_type(SharedCodenameProxyA)
        concrete_b = self._concrete_type(SharedCodenameProxyB)
        proxy_b = self._proxy_type(SharedCodenameProxyB)

        Permission.objects.create(
            content_type=proxy_a,
            codename=SHARED_CODENAME,
            name='already-present-a',
        )
        Permission.objects.create(
            content_type=concrete_b,
            codename=SHARED_CODENAME,
            name='source-b',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_a,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_b,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_b,
                codename=SHARED_CODENAME,
            ).count(),
            0,
        )

    def test_G70_005_keep_same_app_label_proxy_models_isolated_by_content_type_and_codename(self):
        concrete_a = self._concrete_type(SharedCodenameProxyA)
        proxy_a = self._proxy_type(SharedCodenameProxyA)
        concrete_b = self._concrete_type(SharedCodenameProxyB)
        proxy_b = self._proxy_type(SharedCodenameProxyB)

        Permission.objects.create(
            content_type=concrete_a,
            codename=SHARED_CODENAME,
            name='source-a',
        )
        Permission.objects.create(
            content_type=proxy_b,
            codename=SHARED_CODENAME,
            name='already-present-b',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_a,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_b,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_a,
                codename=SHARED_CODENAME,
            ).count(),
            0,
        )

    def test_G70_005_keep_different_app_label_proxy_models_isolated_by_content_type_and_codename(self):
        concrete_a = self._concrete_type(SharedCodenameProxyA)
        proxy_a = self._proxy_type(SharedCodenameProxyA)
        concrete_b = self._concrete_type(CrossAppSharedCodenameProxy)
        proxy_b = self._proxy_type(CrossAppSharedCodenameProxy)

        Permission.objects.create(
            content_type=proxy_a,
            codename=SHARED_CODENAME,
            name='already-present-a',
        )
        Permission.objects.create(
            content_type=concrete_b,
            codename=SHARED_CODENAME,
            name='source-b',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_a,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_b,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_b,
                codename=SHARED_CODENAME,
            ).count(),
            0,
        )

    def test_G70_005_prevent_cross_pollution_for_same_codename_across_content_types(self):
        concrete_a = self._concrete_type(SharedCodenameProxyA)
        proxy_a = self._proxy_type(SharedCodenameProxyA)
        concrete_b = self._concrete_type(CrossAppSharedCodenameProxy)
        proxy_b = self._proxy_type(CrossAppSharedCodenameProxy)

        Permission.objects.create(
            content_type=concrete_a,
            codename=SHARED_CODENAME,
            name='source-a',
        )
        Permission.objects.create(
            content_type=concrete_b,
            codename=SHARED_CODENAME,
            name='source-b',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_a,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_b,
                codename=SHARED_CODENAME,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_a,
                codename=SHARED_CODENAME,
            ).count(),
            0,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_b,
                codename=SHARED_CODENAME,
            ).count(),
            0,
        )
