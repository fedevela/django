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
    ],
    "G70-002": [
        "G70_002UpdateProxyPermissionsTraceabilityTests::test_G70_002_missing_required_proxy_tuple_is_created_exactly_once_during_forward_migration",
        "G70_002UpdateProxyPermissionsTraceabilityTests::test_G70_002_batch_of_missing_proxy_tuples_adds_one_row_each",
        "G70_002UpdateProxyPermissionsTraceabilityTests::test_G70_002_missing_proxy_tuple_inserts_respect_unique_content_type_codename_constraint",
    ],
    "G70-003": [
        "G70_003UpdateProxyPermissionsTraceabilityTests::test_G70_003_forward_rerun_preserves_existing_content_type_and_codename_rowcount",
        "G70_003UpdateProxyPermissionsTraceabilityTests::test_G70_003_forward_rerun_rejects_duplicate_inserts_for_existing_proxy_tuples",
        "G70_003UpdateProxyPermissionsTraceabilityTests::test_G70_003_forward_rerun_keeps_all_required_permissions_present_without_constraint_errors",
    ],
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


class G70_002UpdateProxyPermissionsTraceabilityTests(TestCase):
    available_apps = [
        'auth_tests',
        'django.contrib.auth',
        'django.contrib.contenttypes',
    ]

    def setUp(self):
        Permission.objects.all().delete()

    def test_G70_002_missing_required_proxy_tuple_is_created_exactly_once_during_forward_migration(self):
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        codename = 'display_proxys'

        Permission.objects.create(
            content_type=concrete_content_type,
            codename='add_proxy',
            name='Can add proxy',
        )

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=codename,
            ).count(),
            0,
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=codename,
            ).count(),
            1,
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=codename,
            ).count(),
            1,
        )

    def test_G70_002_batch_of_missing_proxy_tuples_adds_one_row_each(self):
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        missing_permissions = {
            '%s_%s' % (action, Proxy._meta.model_name)
            for action in Proxy._meta.default_permissions
        }
        missing_permissions.update(codename for codename, _name in Proxy._meta.permissions)

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        for codename in sorted(missing_permissions):
            self.assertEqual(
                Permission.objects.filter(
                    content_type=proxy_content_type,
                    codename=codename,
                ).count(),
                1,
            )

    def test_G70_002_missing_proxy_tuple_inserts_respect_unique_content_type_codename_constraint(self):
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)

        Permission.objects.create(
            content_type=concrete_content_type,
            codename='add_proxy',
            name='Can add proxy',
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename='add_proxy',
            ).count(),
            1,
        )


class G70_003UpdateProxyPermissionsTraceabilityTests(TestCase):
    available_apps = [
        'auth_tests',
        'django.contrib.auth',
        'django.contrib.contenttypes',
    ]

    def setUp(self):
        Permission.objects.all().delete()

    def _required_proxy_permissions(self):
        return {
            '%s_%s' % (action, Proxy._meta.model_name)
            for action in Proxy._meta.default_permissions
        }.union(codename for codename, _name in Proxy._meta.permissions)

    def test_G70_003_forward_rerun_preserves_existing_content_type_and_codename_rowcount(self):
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        required_permissions = self._required_proxy_permissions()

        # Simulate a previously migrated database: half the required rows are already
        # present on the proxy content type, the others remain on concrete.
        for codename in sorted(required_permissions):
            Permission.objects.create(
                content_type=concrete_content_type,
                codename=codename,
                name='Concrete permission for %s' % codename,
            )
            if codename.startswith('add_'):
                Permission.objects.create(
                    content_type=proxy_content_type,
                    codename=codename,
                    name='Existing proxy permission for %s' % codename,
                )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        rowcount_before = {
            codename: Permission.objects.filter(
                content_type=proxy_content_type,
                codename=codename,
            ).count()
            for codename in required_permissions
        }

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        for codename in required_permissions:
            self.assertEqual(
                Permission.objects.filter(
                    content_type=proxy_content_type,
                    codename=codename,
                ).count(),
                rowcount_before[codename],
            )

    def test_G70_003_forward_rerun_rejects_duplicate_inserts_for_existing_proxy_tuples(self):
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        required_permissions = self._required_proxy_permissions()

        for codename in sorted(required_permissions):
            Permission.objects.create(
                content_type=concrete_content_type,
                codename=codename,
                name='Concrete permission for %s' % codename,
            )
            Permission.objects.create(
                content_type=proxy_content_type,
                codename=codename,
                name='Existing proxy permission for %s' % codename,
            )

        # Rerun should treat the proxy tuple as already satisfied and perform no
        # extra insert for these already existing codename/content_type combinations.
        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        for codename in required_permissions:
            self.assertEqual(
                Permission.objects.filter(
                    content_type=proxy_content_type,
                    codename=codename,
                ).count(),
                1,
            )

    def test_G70_003_forward_rerun_keeps_all_required_permissions_present_without_constraint_errors(self):
        proxy_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=False)
        concrete_content_type = ContentType.objects.get_for_model(Proxy, for_concrete_model=True)
        required_permissions = self._required_proxy_permissions()

        for codename in sorted(required_permissions):
            Permission.objects.create(
                content_type=concrete_content_type,
                codename=codename,
                name='Clean source permission for %s' % codename,
            )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename='add_proxy',
            ).count(),
            1,
        )

        update_proxy_permissions.update_proxy_model_permissions(apps, None)

        for codename in sorted(required_permissions):
            self.assertEqual(
                Permission.objects.filter(
                    content_type=proxy_content_type,
                    codename=codename,
                ).count(),
                1,
            )
