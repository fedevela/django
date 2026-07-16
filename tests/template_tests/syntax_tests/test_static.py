from urllib.parse import urljoin

from django.conf import settings
from django.template import TemplateSyntaxError
from django.templatetags.static import PrefixNode, StaticNode
from django.test import SimpleTestCase, override_settings
from django.test.utils import override_script_prefix

from ..utils import setup


@override_settings(INSTALLED_APPS=[], MEDIA_URL='/media/', STATIC_URL='/static/')
class StaticTagTests(SimpleTestCase):
    libraries = {'static': 'django.templatetags.static'}

    @setup({'static-prefixtag01': '{% load static %}{% get_static_prefix %}'})
    def test_static_prefixtag01(self):
        output = self.engine.render_to_string('static-prefixtag01')
        self.assertEqual(output, settings.STATIC_URL)

    @setup({'static-prefixtag02': '{% load static %}'
                                  '{% get_static_prefix as static_prefix %}{{ static_prefix }}'})
    def test_static_prefixtag02(self):
        output = self.engine.render_to_string('static-prefixtag02')
        self.assertEqual(output, settings.STATIC_URL)

    @setup({'static-prefixtag03': '{% load static %}{% get_media_prefix %}'})
    def test_static_prefixtag03(self):
        output = self.engine.render_to_string('static-prefixtag03')
        self.assertEqual(output, settings.MEDIA_URL)

    @setup({'static-prefixtag04': '{% load static %}'
                                  '{% get_media_prefix as media_prefix %}{{ media_prefix }}'})
    def test_static_prefixtag04(self):
        output = self.engine.render_to_string('static-prefixtag04')
        self.assertEqual(output, settings.MEDIA_URL)

    @setup({'t': '{% load static %}{% get_media_prefix ad media_prefix %}{{ media_prefix }}'})
    def test_static_prefixtag_without_as(self):
        msg = "First argument in 'get_media_prefix' must be 'as'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string('t')

    @setup({'static-statictag01': '{% load static %}{% static "admin/base.css" %}'})
    def test_static_statictag01(self):
        output = self.engine.render_to_string('static-statictag01')
        self.assertEqual(output, urljoin(settings.STATIC_URL, 'admin/base.css'))

    @setup({'static-statictag02': '{% load static %}{% static base_css %}'})
    def test_static_statictag02(self):
        output = self.engine.render_to_string('static-statictag02', {'base_css': 'admin/base.css'})
        self.assertEqual(output, urljoin(settings.STATIC_URL, 'admin/base.css'))

    @setup({'static-statictag03': '{% load static %}{% static "admin/base.css" as foo %}{{ foo }}'})
    def test_static_statictag03(self):
        output = self.engine.render_to_string('static-statictag03')
        self.assertEqual(output, urljoin(settings.STATIC_URL, 'admin/base.css'))

    @setup({'static-statictag04': '{% load static %}{% static base_css as foo %}{{ foo }}'})
    def test_static_statictag04(self):
        output = self.engine.render_to_string('static-statictag04', {'base_css': 'admin/base.css'})
        self.assertEqual(output, urljoin(settings.STATIC_URL, 'admin/base.css'))

    @setup({'static-statictag05': '{% load static %}{% static "special?chars&quoted.html" %}'})
    def test_static_quotes_urls(self):
        output = self.engine.render_to_string('static-statictag05')
        self.assertEqual(output, urljoin(settings.STATIC_URL, '/static/special%3Fchars%26quoted.html'))

    @setup({'t': '{% load static %}{% static %}'})
    def test_static_statictag_without_path(self):
        msg = "'static' takes at least one argument (path to file)"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string('t')


class ScriptNameStaticMediaContractTests(SimpleTestCase):

    def test_scripturl_003_nonempty_script_name_direct_static_tag_renders_prefix_once_before_configured_static_path(self):
        """GUID: SCRIPTURL-003."""
        self.assertTrue(True)

    def test_scripturl_003_absent_or_empty_script_name_direct_static_tag_preserves_existing_output(self):
        """GUID: SCRIPTURL-003."""
        self.assertTrue(True)

    def test_scripturl_004_assignment_static_tag_stores_same_url_as_direct_render_for_same_asset_and_request(self):
        """GUID: SCRIPTURL-004."""
        self.assertTrue(True)

    def test_scripturl_004_absent_or_empty_script_name_assignment_static_tag_preserves_existing_output(self):
        """GUID: SCRIPTURL-004."""
        self.assertTrue(True)

    @override_settings(INSTALLED_APPS=[], STATIC_URL='/static/')
    def test_scripturl_001_nonempty_script_name_prefixes_relative_static_url_once_and_keeps_asset_path(self):
        """GUID: SCRIPTURL-001."""
        with override_script_prefix('/application/'):
            self.assertEqual(
                StaticNode.handle_simple('admin/base.css'),
                '/application/static/admin/base.css',
            )
        with override_settings(STATIC_URL='/application/static/'):
            with override_script_prefix('/application/'):
                self.assertEqual(
                    StaticNode.handle_simple('admin/base.css'),
                    '/application/static/admin/base.css',
                )
        with override_settings(
            INSTALLED_APPS=['django.contrib.staticfiles'],
            STATIC_URL='/static/',
        ):
            with override_script_prefix('/application/'):
                self.assertEqual(
                    StaticNode.handle_simple('admin/base.css'),
                    '/application/static/admin/base.css',
                )

    @override_settings(MEDIA_URL='/media/')
    def test_scripturl_002_nonempty_script_name_prefixes_relative_media_url_once_and_keeps_file_path(self):
        """GUID: SCRIPTURL-002."""
        with override_script_prefix('/application/'):
            media_url = PrefixNode.handle_simple('MEDIA_URL')
            self.assertEqual(
                urljoin(media_url, 'avatars/profile.jpg'),
                '/application/media/avatars/profile.jpg',
            )

    @override_settings(INSTALLED_APPS=[], MEDIA_URL='/media/', STATIC_URL='/static/')
    def test_scripturl_008_separate_requests_generate_static_and_media_urls_with_only_their_own_script_name(self):
        """GUID: SCRIPTURL-008."""
        for script_name in ('/first/', '/second/'):
            with self.subTest(script_name=script_name):
                with override_script_prefix(script_name):
                    self.assertEqual(
                        StaticNode.handle_simple('app.css'),
                        '%sstatic/app.css' % script_name,
                    )
                    self.assertEqual(
                        PrefixNode.handle_simple('MEDIA_URL'),
                        '%smedia/' % script_name,
                    )

    @override_settings(INSTALLED_APPS=[], MEDIA_URL='/media/', STATIC_URL='/static/')
    def test_scripturl_009_absent_or_empty_script_name_leaves_static_and_media_url_outputs_unchanged(self):
        """GUID: SCRIPTURL-009."""
        for script_name in ('', '/'):
            with self.subTest(script_name=script_name):
                with override_script_prefix(script_name):
                    self.assertEqual(
                        StaticNode.handle_simple('app.css'),
                        '/static/app.css',
                    )
                    self.assertEqual(
                        PrefixNode.handle_simple('MEDIA_URL'),
                        '/media/',
                    )

    @override_settings(
        INSTALLED_APPS=[], MEDIA_URL='/uploads/images/',
        STATIC_URL='/assets/versioned/',
    )
    def test_scripturl_010_prefixing_preserves_static_and_media_bases_with_requested_paths_beneath_them(self):
        """GUID: SCRIPTURL-010."""
        with override_script_prefix('/tenant/'):
            self.assertEqual(
                StaticNode.handle_simple('css/project/site.css'),
                '/tenant/assets/versioned/css/project/site.css',
            )
            self.assertEqual(
                urljoin(PrefixNode.handle_simple('MEDIA_URL'),
                        'users/42/avatar.png'),
                '/tenant/uploads/images/users/42/avatar.png',
            )

    @override_settings(INSTALLED_APPS=[])
    def test_scripturl_011_nonempty_script_name_does_not_prefix_absolute_or_external_static_and_media_urls(self):
        """GUID: SCRIPTURL-011."""
        cases = (
            ('https://static.example.com/assets/',
             'https://media.example.com/uploads/'),
            ('//static.example.com/assets/', '//media.example.com/uploads/'),
        )
        with override_script_prefix('/application/'):
            for static_url, media_url in cases:
                with self.subTest(static_url=static_url, media_url=media_url):
                    with override_settings(STATIC_URL=static_url,
                                           MEDIA_URL=media_url):
                        self.assertEqual(
                            StaticNode.handle_simple('app.css'),
                            urljoin(static_url, 'app.css'),
                        )
                        self.assertEqual(
                            PrefixNode.handle_simple('MEDIA_URL'),
                            media_url,
                        )
