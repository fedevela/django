from importlib import import_module
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from .models import Proxy


update_proxy_permissions = import_module(
    'django.contrib.auth.migrations.0011_update_proxy_permissions'
)

G70_001_REQUIREMENT_TO_VERIFICATION = {
    "G70-001": [
        "G70_001UpdateProxyPermissionsTraceabilityTests::test_G70_001_existing_tuple_rowcount_for_content_type_codename_is_preserved",
        "G70_001UpdateProxyPermissionsTraceabilityTests::test_G70_001_existing_tuple_is_detected_without_integrity_error",
        "G70_001UpdateProxyPermissionsTraceabilityTests::test_G70_001_mixed_present_and_missing_tuples_preserve_existing_rows",
    ]
}


class G70_001UpdateProxyPermissionsTraceabilityTests(TestCase):
    available_apps = [
        'auth_tests',
        'django.contrib.auth',
        'django.contrib.contenttypes',
    ]

    def setUp(self):
        Permission.objects.all().delete()

    def test_G70_001_existing_tuple_rowcount_for_content_type_codename_is_preserved(self):
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        codename = 'add_proxy'

        Permission.objects.create(
            content_type=concrete_content_type,
            codename=codename,
            name='Can add proxy',
        )
        Permission.objects.create(
            content_type=proxy_content_type,
            codename=codename,
            name='Existing proxy permission',
        )

        concrete_count_before = Permission.objects.filter(
            content_type=concrete_content_type,
            codename=codename,
        ).count()
        proxy_count_before = Permission.objects.filter(
            content_type=proxy_content_type,
            codename=codename,
        ).count()

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=codename,
            ).count(),
            proxy_count_before,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_content_type,
                codename=codename,
            ).count(),
            concrete_count_before,
        )

    def test_G70_001_existing_tuple_is_detected_without_integrity_error(self):
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)

        Permission.objects.create(
            content_type=concrete_content_type,
            codename='add_proxy',
            name='Can add proxy',
        )
        Permission.objects.create(
            content_type=proxy_content_type,
            codename='add_proxy',
            name='Existing proxy permission',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(Permission.objects.filter(codename='add_proxy').count(), 2)

    def test_G70_001_mixed_present_and_missing_tuples_preserve_existing_rows(self):
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)

        Permission.objects.create(
            content_type=concrete_content_type,
            codename='add_proxy',
            name='Can add proxy',
        )
        Permission.objects.create(
            content_type=proxy_content_type,
            codename='add_proxy',
            name='Existing proxy permission',
        )
        Permission.objects.create(
            content_type=concrete_content_type,
            codename='display_proxys',
            name='May display proxys information',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_content_type,
                codename='add_proxy',
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename='add_proxy',
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_content_type,
                codename='display_proxys',
            ).count(),
            0,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename='display_proxys',
            ).count(),
            1,
        )
