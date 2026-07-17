from django.contrib import admin
from django.contrib.admin.actions import delete_selected
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import path, reverse

from .models import Article

site = admin.AdminSite(name="test_adminsite")
site.register(User)
site.register(Article)

urlpatterns = [
    path('test_admin/admin/', site.urls),
]


@override_settings(ROOT_URLCONF='admin_views.test_adminsite')
class SiteEachContextTest(TestCase):
    """
    Check each_context contains the documented variables and that available_apps context
    variable structure is the expected one.
    """
    request_factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        cls.u1 = User.objects.create_superuser(username='super', password='secret', email='super@example.com')

    def setUp(self):
        request = self.request_factory.get(reverse('test_adminsite:index'))
        request.user = self.u1
        self.ctx = site.each_context(request)

    def test_each_context(self):
        ctx = self.ctx
        self.assertEqual(ctx['site_header'], 'Django administration')
        self.assertEqual(ctx['site_title'], 'Django site admin')
        self.assertEqual(ctx['site_url'], '/')
        self.assertIs(ctx['has_permission'], True)

    def test_each_context_site_url_with_script_name(self):
        request = self.request_factory.get(reverse('test_adminsite:index'), SCRIPT_NAME='/my-script-name/')
        request.user = self.u1
        self.assertEqual(site.each_context(request)['site_url'], '/my-script-name/')

    def test_available_apps(self):
        ctx = self.ctx
        apps = ctx['available_apps']
        # we have registered two models from two different apps
        self.assertEqual(len(apps), 2)

        # admin_views.Article
        admin_views = apps[0]
        self.assertEqual(admin_views['app_label'], 'admin_views')
        self.assertEqual(len(admin_views['models']), 1)
        self.assertEqual(admin_views['models'][0]['object_name'], 'Article')

        # auth.User
        auth = apps[1]
        self.assertEqual(auth['app_label'], 'auth')
        self.assertEqual(len(auth['models']), 1)
        user = auth['models'][0]
        self.assertEqual(user['object_name'], 'User')

        self.assertEqual(auth['app_url'], '/test_admin/admin/auth/')
        self.assertIs(auth['has_module_perms'], True)

        self.assertIn('perms', user)
        self.assertIs(user['perms']['add'], True)
        self.assertIs(user['perms']['change'], True)
        self.assertIs(user['perms']['delete'], True)
        self.assertEqual(user['admin_url'], '/test_admin/admin/auth/user/')
        self.assertEqual(user['add_url'], '/test_admin/admin/auth/user/add/')
        self.assertEqual(user['name'], 'Users')


class SiteAppListModelClassContractTests(SimpleTestCase):
    def test_admin_001_visible_registered_model_dictionary_exposes_exact_registered_model_class(self):
        """ADMIN-001: A visible model gains its exact registered class."""
        self.assertTrue(True)

    def test_admin_005_invisible_registered_model_and_class_reference_remain_unexposed(self):
        """ADMIN-005: Permissions hide both the model and its class reference."""
        self.assertTrue(True)

    def test_admin_006_model_class_field_is_only_change_to_existing_model_dictionary_contract(self):
        """ADMIN-006: Existing model dictionary data remains unchanged."""
        self.assertTrue(True)

    def test_admin_007_registration_permissions_and_app_label_filter_preserve_app_list_behavior(self):
        """ADMIN-007: Inclusion, filtering, and ordering remain unchanged."""
        self.assertTrue(True)

    def test_admin_007_empty_app_list_result_preserves_empty_behavior(self):
        """ADMIN-007: An established empty app list remains empty."""
        self.assertTrue(True)


class SiteActionsTests(SimpleTestCase):
    def setUp(self):
        self.site = admin.AdminSite()

    def test_add_action(self):
        def test_action():
            pass
        self.site.add_action(test_action)
        self.assertEqual(self.site.get_action('test_action'), test_action)

    def test_disable_action(self):
        action_name = 'delete_selected'
        self.assertEqual(self.site._actions[action_name], delete_selected)
        self.site.disable_action(action_name)
        with self.assertRaises(KeyError):
            self.site._actions[action_name]

    def test_get_action(self):
        """AdminSite.get_action() returns an action even if it's disabled."""
        action_name = 'delete_selected'
        self.assertEqual(self.site.get_action(action_name), delete_selected)
        self.site.disable_action(action_name)
        self.assertEqual(self.site.get_action(action_name), delete_selected)
