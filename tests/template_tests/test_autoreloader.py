from pathlib import Path
from unittest import mock

from django.template import autoreload
from django.test import SimpleTestCase, override_settings
from django.test.utils import require_jinja2
from django.utils import autoreload as utils_autoreload

ROOT = Path(__file__).parent.absolute()
EXTRA_TEMPLATES_DIR = ROOT / "templates_extra"


@override_settings(
    INSTALLED_APPS=['template_tests'],
    TEMPLATES=[{
        'BACKEND': 'django.template.backends.dummy.TemplateStrings',
        'APP_DIRS': True,
    }, {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [EXTRA_TEMPLATES_DIR],
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]
        },
    }])
class TemplateReloadTests(SimpleTestCase):
    @mock.patch('django.template.autoreload.reset_loaders')
    def test_template_changed(self, mock_reset):
        template_path = Path(__file__).parent / 'templates' / 'index.html'
        self.assertTrue(autoreload.template_changed(None, template_path))
        mock_reset.assert_called_once()

    @mock.patch('django.template.autoreload.reset_loaders')
    def test_non_template_changed(self, mock_reset):
        self.assertIsNone(autoreload.template_changed(None, Path(__file__)))
        mock_reset.assert_not_called()

    def test_watch_for_template_changes(self):
        mock_reloader = mock.MagicMock()
        autoreload.watch_for_template_changes(mock_reloader)
        self.assertSequenceEqual(
            sorted(mock_reloader.watch_dir.call_args_list),
            [
                mock.call(ROOT / 'templates', '**/*'),
                mock.call(ROOT / 'templates_extra', '**/*')
            ]
        )

    def test_get_template_directories(self):
        self.assertSetEqual(
            autoreload.get_template_directories(),
            {
                ROOT / 'templates_extra',
                ROOT / 'templates',
            }
        )

    @mock.patch('django.template.loaders.base.Loader.reset')
    def test_reset_all_loaders(self, mock_reset):
        autoreload.reset_loaders()
        self.assertEqual(mock_reset.call_count, 2)

    @override_settings(
        TEMPLATES=[{
            'DIRS': [
                str(ROOT) + '/absolute_str',
                'template_tests/relative_str',
                Path('template_tests/relative_path'),
            ],
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
        }]
    )
    def test_template_dirs_normalized_to_paths(self):
        self.assertSetEqual(
            autoreload.get_template_directories(),
            {
                ROOT / 'absolute_str',
                Path.cwd() / 'template_tests/relative_str',
                Path.cwd() / 'template_tests/relative_path',
            }
        )


@override_settings(
    TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [ROOT],
    }],
)
class EncompassingTemplateDirectoryTests(SimpleTestCase):
    @mock.patch('django.template.autoreload.reset_loaders')
    @mock.patch('django.utils.autoreload.trigger_reload')
    def test_arld_002_saving_settings_in_base_dir_template_dirs_triggers_autoreload(
        self, mock_trigger_reload, mock_reset_loaders,
    ):
        """ARLD-002: Saving settings.py under a BASE_DIR template dir reloads."""
        settings_file = ROOT / 'settings.py'

        utils_autoreload.BaseReloader().notify_file_changed(settings_file)

        mock_trigger_reload.assert_called_once_with(settings_file)
        mock_reset_loaders.assert_not_called()

    @mock.patch('django.utils.autoreload.trigger_reload')
    def test_arld_001_saving_monitored_non_template_file_in_base_dir_triggers_autoreload(self, mock_trigger_reload):
        """ARLD-001: Saving a monitored non-template file triggers autoreload."""
        project_file = ROOT / 'project_file.py'

        utils_autoreload.BaseReloader().notify_file_changed(project_file)

        mock_trigger_reload.assert_called_once_with(project_file)

    @mock.patch('django.template.autoreload.reset_loaders')
    def test_arld_003_encompassing_template_dir_preserves_overlapping_project_file_monitoring(
        self, mock_reset_loaders,
    ):
        """ARLD-003: An encompassing template dir preserves project monitoring."""
        project_file = ROOT / 'project_file.py'

        self.assertIsNone(autoreload.template_changed(None, project_file))

        mock_reset_loaders.assert_not_called()

    @mock.patch('django.utils.autoreload.trigger_reload')
    def test_arld_004_valid_accessible_base_dir_remains_supported_while_autoreload_is_active(
        self, mock_trigger_reload,
    ):
        """ARLD-004: An accessible BASE_DIR remains supported during autoreload."""
        reloader = utils_autoreload.BaseReloader()
        autoreload.watch_for_template_changes(reloader)

        self.assertEqual(reloader.directory_globs[ROOT], {'**/*'})
        project_file = ROOT / 'project_file.py'
        reloader.notify_file_changed(project_file)
        mock_trigger_reload.assert_called_once_with(project_file)


@require_jinja2
@override_settings(INSTALLED_APPS=['template_tests'])
class Jinja2TemplateReloadTests(SimpleTestCase):
    def test_watch_for_template_changes(self):
        mock_reloader = mock.MagicMock()
        autoreload.watch_for_template_changes(mock_reloader)
        self.assertSequenceEqual(
            sorted(mock_reloader.watch_dir.call_args_list),
            [
                mock.call(ROOT / 'templates', '**/*'),
            ]
        )

    def test_get_template_directories(self):
        self.assertSetEqual(
            autoreload.get_template_directories(),
            {
                ROOT / 'templates',
            }
        )

    @mock.patch('django.template.loaders.base.Loader.reset')
    def test_reset_all_loaders(self, mock_reset):
        autoreload.reset_loaders()
        self.assertEqual(mock_reset.call_count, 0)
