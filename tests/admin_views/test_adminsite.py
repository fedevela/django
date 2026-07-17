from unittest.mock import Mock

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


@override_settings(ROOT_URLCONF='admin_views.test_adminsite')
class SiteAppListModelClassContractTests(SimpleTestCase):
    request_factory = RequestFactory()

    def request_with_permissions(self, has_permissions):
        request = self.request_factory.get('/test_admin/admin/')
        request.user = Mock()
        request.user.has_module_perms.return_value = True
        request.user.has_perm.return_value = has_permissions
        return request

    def test_admin_001_visible_registered_model_dictionary_exposes_exact_registered_model_class(self):
        """ADMIN-001: A visible model gains its exact registered class."""
        app_list = site.get_app_list(self.request_with_permissions(True))

        models = {
            model['object_name']: model
            for app in app_list
            for model in app['models']
        }
        self.assertIs(models['Article']['model'], Article)
        self.assertIs(models['User']['model'], User)

    def test_admin_005_invisible_registered_model_and_class_reference_remain_unexposed(self):
        """ADMIN-005: Permissions hide both the model and its class reference."""
        request = self.request_with_permissions(False)

        self.assertEqual(site.build_app_dict(request), {})
        self.assertEqual(site.get_app_list(request), [])

    def test_admin_006_model_class_field_is_only_change_to_existing_model_dictionary_contract(self):
        """ADMIN-006: Existing model dictionary data remains unchanged."""
        app = site.build_app_dict(
            self.request_with_permissions(True), label='admin_views',
        )

        self.assertEqual(len(app['models']), 1)
        model_dict = app['models'][0]
        self.assertEqual(set(model_dict), {
            'model', 'name', 'object_name', 'perms', 'admin_url', 'add_url',
            'view_only',
        })
        self.assertIs(model_dict['model'], Article)
        self.assertEqual(model_dict['name'], 'Articles')
        self.assertEqual(model_dict['object_name'], 'Article')
        self.assertEqual(model_dict['perms'], {
            'add': True,
            'change': True,
            'delete': True,
            'view': True,
        })
        self.assertEqual(
            model_dict['admin_url'],
            '/test_admin/admin/admin_views/article/',
        )
        self.assertEqual(
            model_dict['add_url'],
            '/test_admin/admin/admin_views/article/add/',
        )
        self.assertIs(model_dict['view_only'], False)

    def test_admin_007_registration_permissions_and_app_label_filter_preserve_app_list_behavior(self):
        """ADMIN-007: Inclusion, filtering, and ordering remain unchanged."""
        request = self.request_with_permissions(True)

        app_list = site.get_app_list(request)
        self.assertEqual(
            [app['app_label'] for app in app_list],
            ['admin_views', 'auth'],
        )
        auth_app = site.build_app_dict(request, label='auth')
        self.assertEqual(auth_app['app_label'], 'auth')
        self.assertEqual(len(auth_app['models']), 1)
        self.assertIs(auth_app['models'][0]['model'], User)
        self.assertIsNone(site.build_app_dict(request, label='sessions'))

    def test_admin_007_empty_app_list_result_preserves_empty_behavior(self):
        """ADMIN-007: An established empty app list remains empty."""
        empty_site = admin.AdminSite(name='empty')

        self.assertEqual(
            empty_site.get_app_list(self.request_with_permissions(True)),
            [],
        )


@override_settings(ROOT_URLCONF='admin_views.test_adminsite')
class SiteBuildAppDictPublicMethodContractTests(SimpleTestCase):
    request_factory = RequestFactory()

    def request_with_permissions(self):
        request = self.request_factory.get('/test_admin/admin/')
        request.user = Mock()
        request.user.has_module_perms.return_value = True
        request.user.has_perm.return_value = True
        return request

    def test_admin_002_valid_request_without_app_label_returns_unfiltered_app_dictionary(self):
        """ADMIN-002: The public builder preserves unfiltered invocation."""
        app_dict = site.build_app_dict(self.request_with_permissions())

        self.assertEqual(set(app_dict), {'admin_views', 'auth'})
        self.assertEqual(app_dict['admin_views']['app_label'], 'admin_views')
        self.assertEqual(app_dict['auth']['app_label'], 'auth')

    def test_admin_002_valid_request_with_app_label_returns_filtered_app_dictionary(self):
        """ADMIN-002: The public builder preserves app-label filtering."""
        app = site.build_app_dict(
            self.request_with_permissions(), label='admin_views',
        )

        self.assertEqual(app['app_label'], 'admin_views')
        self.assertEqual(
            [model['object_name'] for model in app['models']],
            ['Article'],
        )

    def test_admin_002_admin_site_exposes_callable_public_app_dictionary_builder(self):
        """ADMIN-002: The app-dictionary builder has a callable public name."""
        self.assertTrue(callable(site.build_app_dict))


class SiteIndexPublicAppDictionaryBuilderContractTests(SimpleTestCase):
    def test_admin_003_main_admin_index_obtains_app_dictionary_through_public_builder(self):
        """ADMIN-003: The main index obtains its dictionary publicly."""
        admin_site = admin.AdminSite(name='index_builder')
        request = RequestFactory().get('/index/')
        admin_site.each_context = Mock(return_value={})
        admin_site.build_app_dict = Mock(return_value={})

        response = admin_site.index(request)

        admin_site.build_app_dict.assert_called_once_with(request)
        self.assertEqual(response.context_data['app_list'], [])

    def test_admin_003_public_builder_full_dictionary_flows_to_index_app_list_without_behavior_change(self):
        """ADMIN-003: The builder result reaches the established app list."""
        admin_site = admin.AdminSite(name='index_builder_result')
        request = RequestFactory().get('/index/')
        admin_site.each_context = Mock(return_value={})
        article = {'name': 'Articles'}
        group = {'name': 'Groups'}
        user = {'name': 'Users'}
        app_dict = {
            'auth': {'name': 'Authentication', 'models': [user, group]},
            'admin_views': {'name': 'Admin views', 'models': [article]},
        }
        admin_site.build_app_dict = Mock(return_value=app_dict)

        response = admin_site.index(request)

        self.assertEqual(
            response.context_data['app_list'],
            [app_dict['admin_views'], app_dict['auth']],
        )
        self.assertEqual(app_dict['auth']['models'], [group, user])


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
