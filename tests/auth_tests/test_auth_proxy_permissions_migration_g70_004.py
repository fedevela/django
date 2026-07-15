from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from .models import Proxy, UserProxy


update_proxy_permissions = import_module(
    'django.contrib.auth.migrations.0011_update_proxy_permissions'
)


G70_004_REQUIREMENT_TO_VERIFICATION = {
    "G70-004": [
        "G70_004UpdateProxyPermissionsTraceabilityTests::test_G70_004_auth_0011_completes_from_2_0_13_upgrade_without_unique_constraint_integrityerror",
        "G70_004UpdateProxyPermissionsTraceabilityTests::test_G70_004_auth_0011_completes_when_proxy_permission_rows_preexist_without_manual_cleanup",
        "G70_004UpdateProxyPermissionsTraceabilityTests::test_G70_004_auth_0011_completes_with_same_and_different_app_label_proxy_changes",
    ],
}


class G70_004UpdateProxyPermissionsTraceabilityTests(TestCase):
    available_apps = [
        "auth_tests",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    def setUp(self):
        Permission.objects.all().delete()

    def _required_permissions(self, model):
        return {
            '%s_%s' % (action, model._meta.model_name)
            for action in model._meta.default_permissions
        }.union(codename for codename, _name in model._meta.permissions)

    def test_G70_004_auth_0011_completes_from_2_0_13_upgrade_without_unique_constraint_integrityerror(self):
        concrete_proxy_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        concrete_user_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=True)
        userproxy_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=False)

        proxy_permissions = self._required_permissions(Proxy)
        user_permissions = self._required_permissions(UserProxy)

        for codename in proxy_permissions:
            Permission.objects.create(
                content_type=concrete_proxy_type,
                codename=codename,
                name='legacy proxy source',
            )
        for codename in user_permissions:
            Permission.objects.create(
                content_type=concrete_user_type,
                codename=codename,
                name='legacy userproxy source',
            )

        # Simulate stale rows that were already upgraded in one historical leg.
        Permission.objects.create(
            content_type=proxy_type,
            codename=next(iter(proxy_permissions)),
            name='already upgraded proxy row',
        )
        Permission.objects.create(
            content_type=userproxy_type,
            codename=next(iter(user_permissions)),
            name='already upgraded userproxy row',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        for codename in proxy_permissions:
            self.assertEqual(
                Permission.objects.filter(content_type=proxy_type, codename=codename).count(),
                1,
            )
        for codename in user_permissions:
            self.assertEqual(
                Permission.objects.filter(content_type=userproxy_type, codename=codename).count(),
                1,
            )

    def test_G70_004_auth_0011_completes_when_proxy_permission_rows_preexist_without_manual_cleanup(self):
        concrete_proxy_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        concrete_user_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=True)
        userproxy_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=False)

        proxy_permissions = self._required_permissions(Proxy)
        user_permissions = self._required_permissions(UserProxy)
        first_proxy_permission = next(iter(proxy_permissions))
        first_user_permission = next(iter(user_permissions))

        # Leave legacy source rows and pre-created target rows to emulate historical
        # manual cleanup guidance that should no longer be required.
        Permission.objects.create(
            content_type=proxy_type,
            codename=first_proxy_permission,
            name='already present proxy target',
        )
        Permission.objects.create(
            content_type=userproxy_type,
            codename=first_user_permission,
            name='already present userproxy target',
        )

        for codename in proxy_permissions:
            Permission.objects.create(
                content_type=concrete_proxy_type,
                codename=codename,
                name='legacy proxy source',
            )
        for codename in user_permissions:
            Permission.objects.create(
                content_type=concrete_user_type,
                codename=codename,
                name='legacy userproxy source',
            )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_type,
                codename=first_proxy_permission,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=userproxy_type,
                codename=first_user_permission,
            ).count(),
            1,
        )
        for codename in proxy_permissions:
            self.assertEqual(
                Permission.objects.filter(content_type=proxy_type, codename=codename).count(),
                1,
            )
        for codename in user_permissions:
            self.assertEqual(
                Permission.objects.filter(content_type=userproxy_type, codename=codename).count(),
                1,
            )

    def test_G70_004_auth_0011_completes_with_same_and_different_app_label_proxy_changes(self):
        concrete_proxy_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        concrete_user_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=True)
        userproxy_type = ContentType.objects.get_for_model(UserProxy, for_concrete_model=False)

        proxy_permissions = sorted(self._required_permissions(Proxy))
        user_permissions = sorted(self._required_permissions(UserProxy))

        # Same-app-label transition starts with one upgraded tuple and missing source rows.
        Permission.objects.create(
            content_type=proxy_type,
            codename=proxy_permissions[0],
            name='already upgraded proxy',
        )
        for codename in proxy_permissions[1:]:
            Permission.objects.create(
                content_type=concrete_proxy_type,
                codename=codename,
                name='legacy proxy source',
            )

        # Different-app-label transition mirrors the same mixed state.
        Permission.objects.create(
            content_type=userproxy_type,
            codename=user_permissions[0],
            name='already upgraded userproxy',
        )
        for codename in user_permissions[1:]:
            Permission.objects.create(
                content_type=concrete_user_type,
                codename=codename,
                name='legacy userproxy source',
            )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        for codename in proxy_permissions:
            self.assertEqual(
                Permission.objects.filter(content_type=proxy_type, codename=codename).count(),
                1,
            )
        for codename in user_permissions:
            self.assertEqual(
                Permission.objects.filter(content_type=userproxy_type, codename=codename).count(),
                1,
            )
