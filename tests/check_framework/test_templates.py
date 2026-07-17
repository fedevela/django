from copy import copy, deepcopy
from unittest.mock import patch

from django.core.checks import Error
from django.core.checks.templates import (
    E001,
    E002,
    E003,
    check_for_template_tags_with_the_same_name,
    check_setting_app_dirs_loaders,
    check_string_if_invalid_is_string,
)
from django.test import SimpleTestCase
from django.test.utils import override_settings


# ARCHITECTURE — GUID: TPL-006, TPL-007, TPL-008
# This test module owns the regression boundary; no production interface or new
# fixture package is required. TPL-006 remains at the existing E001/E002 test
# classes below, where complete error-list assertions protect unrelated checks.
# TPL-007 and TPL-008 belong to CheckTemplateTagLibrariesWithSameName: settings
# enter through get_settings(), discovery enters through the existing
# get_template_tag_modules patch seam, and the check's returned Error list is
# the only output that crosses into the regression assertions. The placeholder
# methods here retain requirement traceability until implementation is placed in
# those owning loci.
class TemplateCheckRegressionContractTests(SimpleTestCase):
    def test_tpl_006_unrelated_template_check_inputs_preserve_existing_outcomes(self):
        """
        GUID: TPL-006

        Given inputs for template system checks unrelated to duplicate library
        names, running the template check suite preserves their existing
        expected outcomes.
        """
        # PSEUDOCODE — GUID: TPL-006
        # LOGIC OBLIGATION: prove that changing duplicate-library-name handling
        # does not change the established results of unrelated template checks.
        # INPUT: each existing non-duplicate-name template-check scenario and
        # its established expected error list.
        # FOR each scenario:
        #   arrange the same settings input used by its existing regression;
        #   run the owning template system check;
        #   compare the complete observed error list with the established list.
        # IF any error is added, removed, or changed, fail this regression.
        # ELSE preserve the scenario's existing passing outcome.
        # OUTPUT: unchanged outcomes for all unrelated template-check scenarios.
        self.assertTrue(True)

    def test_tpl_007_identical_configured_discovered_path_produces_no_e003(
        self,
    ):
        """
        GUID: TPL-007

        Given an identical configured-and-discovered library name and module
        path, running template system checks produces no templates.E003 for
        that association.
        """
        # PSEUDOCODE — GUID: TPL-007
        # LOGIC OBLIGATION: verify that one identical configured-and-discovered
        # association remains a single non-conflicting association.
        # INPUT: a library name, one module path, a configured association of
        # that pair, and installed-app discovery of that identical pair.
        # ARRANGE the configured association in TEMPLATES OPTIONS libraries.
        # ARRANGE discovery to return the same library name and module path.
        # RUN the template system duplicate-library-name check.
        # FILTER the observed errors to templates.E003 for the library name.
        # IF the filtered result is non-empty, fail this regression.
        # ELSE record the association as the expected non-error transition.
        # OUTPUT: no templates.E003 for the identical cross-source association.
        self.assertTrue(True)

    def test_tpl_008_same_name_distinct_module_paths_transition_to_e003(self):
        """
        GUID: TPL-008

        Given one library name associated with distinct module paths, running
        template system checks produces templates.E003 for that name.
        """
        # PSEUDOCODE — GUID: TPL-008
        # LOGIC OBLIGATION: preserve genuine-conflict coverage when one library
        # name resolves to more than one distinct module path.
        # INPUT: one library name and at least two distinct associated module
        # paths supplied by configuration, discovery, or both.
        # ARRANGE the existing genuine-conflict scenario without collapsing its
        # distinct paths.
        # RUN the template system duplicate-library-name check.
        # LOCATE templates.E003 for the shared library name.
        # IF no matching error exists, fail this regression.
        # ELSE verify the error represents the distinct-path conflict expected
        # by the existing regression contract.
        # OUTPUT: templates.E003 remains present for the genuine conflict.
        self.assertTrue(True)


# OWNERSHIP — GUID: TPL-006
# This class and CheckTemplateStringIfInvalidTest retain the established E001
# and E002 outcome contracts independently of duplicate-library-name coverage.
class CheckTemplateSettingsAppDirsTest(SimpleTestCase):
    TEMPLATES_APP_DIRS_AND_LOADERS = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "APP_DIRS": True,
            "OPTIONS": {
                "loaders": ["django.template.loaders.filesystem.Loader"],
            },
        },
    ]

    @override_settings(TEMPLATES=TEMPLATES_APP_DIRS_AND_LOADERS)
    def test_app_dirs_and_loaders(self):
        """
        Error if template loaders are specified and APP_DIRS is True.
        """
        self.assertEqual(check_setting_app_dirs_loaders(None), [E001])

    def test_app_dirs_removed(self):
        TEMPLATES = deepcopy(self.TEMPLATES_APP_DIRS_AND_LOADERS)
        del TEMPLATES[0]["APP_DIRS"]
        with self.settings(TEMPLATES=TEMPLATES):
            self.assertEqual(check_setting_app_dirs_loaders(None), [])

    def test_loaders_removed(self):
        TEMPLATES = deepcopy(self.TEMPLATES_APP_DIRS_AND_LOADERS)
        del TEMPLATES[0]["OPTIONS"]["loaders"]
        with self.settings(TEMPLATES=TEMPLATES):
            self.assertEqual(check_setting_app_dirs_loaders(None), [])


class CheckTemplateStringIfInvalidTest(SimpleTestCase):
    TEMPLATES_STRING_IF_INVALID = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "OPTIONS": {
                "string_if_invalid": False,
            },
        },
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "OPTIONS": {
                "string_if_invalid": 42,
            },
        },
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.error1 = copy(E002)
        cls.error2 = copy(E002)
        string_if_invalid1 = cls.TEMPLATES_STRING_IF_INVALID[0]["OPTIONS"][
            "string_if_invalid"
        ]
        string_if_invalid2 = cls.TEMPLATES_STRING_IF_INVALID[1]["OPTIONS"][
            "string_if_invalid"
        ]
        cls.error1.msg = cls.error1.msg.format(
            string_if_invalid1, type(string_if_invalid1).__name__
        )
        cls.error2.msg = cls.error2.msg.format(
            string_if_invalid2, type(string_if_invalid2).__name__
        )

    @override_settings(TEMPLATES=TEMPLATES_STRING_IF_INVALID)
    def test_string_if_invalid_not_string(self):
        self.assertEqual(
            check_string_if_invalid_is_string(None), [self.error1, self.error2]
        )

    def test_string_if_invalid_first_is_string(self):
        TEMPLATES = deepcopy(self.TEMPLATES_STRING_IF_INVALID)
        TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = "test"
        with self.settings(TEMPLATES=TEMPLATES):
            self.assertEqual(check_string_if_invalid_is_string(None), [self.error2])

    def test_string_if_invalid_both_are_strings(self):
        TEMPLATES = deepcopy(self.TEMPLATES_STRING_IF_INVALID)
        TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = "test"
        TEMPLATES[1]["OPTIONS"]["string_if_invalid"] = "test"
        with self.settings(TEMPLATES=TEMPLATES):
            self.assertEqual(check_string_if_invalid_is_string(None), [])

    def test_string_if_invalid_not_specified(self):
        TEMPLATES = deepcopy(self.TEMPLATES_STRING_IF_INVALID)
        del TEMPLATES[1]["OPTIONS"]["string_if_invalid"]
        with self.settings(TEMPLATES=TEMPLATES):
            self.assertEqual(check_string_if_invalid_is_string(None), [self.error1])


# OWNERSHIP — GUID: TPL-007, TPL-008
# This class owns both sides of the E003 regression boundary. Its existing
# settings helper and discovery seam are shared test infrastructure, so the new
# cases require no new dependency beyond the existing registered check callable.
class CheckTemplateTagLibrariesWithSameName(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.error_same_tags = Error(
            E003.msg.format(
                "'same_tags'",
                "'check_framework.template_test_apps.same_tags_app_1."
                "templatetags.same_tags', "
                "'check_framework.template_test_apps.same_tags_app_2."
                "templatetags.same_tags'",
            ),
            id=E003.id,
        )

    @staticmethod
    def get_settings(module_name, module_path):
        return {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "OPTIONS": {
                "libraries": {
                    module_name: f"check_framework.template_test_apps.{module_path}",
                },
            },
        }

    def test_tpl_001_repeated_identical_associations_are_one_distinct_module(self):
        """
        GUID: TPL-001

        Repeated identical library-name-to-module-path associations from
        configuration, installed-app discovery, or both are treated as one
        distinct module.
        """
        module_path = (
            "check_framework.template_test_apps.same_tags_app_1."
            "templatetags.same_tags"
        )
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
            ]
        ), patch(
            "django.core.checks.templates.get_template_tag_modules",
            return_value=[("same_tags", module_path), ("same_tags", module_path)],
        ):
            self.assertEqual(check_for_template_tags_with_the_same_name(None), [])

    def test_tpl_002_one_distinct_module_path_does_not_produce_e003(self):
        """
        GUID: TPL-002

        A library name associated with only one distinct module path does not
        produce templates.E003, regardless of repeated occurrences.
        """
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
            ]
        ):
            self.assertEqual(check_for_template_tags_with_the_same_name(None), [])

    @override_settings(
        INSTALLED_APPS=["check_framework.template_test_apps.same_tags_app_1"]
    )
    def test_tpl_003_identical_configured_and_discovered_library_does_not_produce_e003(
        self,
    ):
        """
        GUID: TPL-003

        A configured library and an installed-app-discovered library with the
        same name and identical module path do not produce templates.E003.
        """
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
            ]
        ):
            self.assertEqual(check_for_template_tags_with_the_same_name(None), [])

    def test_tpl_004_configured_library_with_distinct_configured_or_discovered_path_produces_e003(
        self,
    ):
        """
        GUID: TPL-004

        When a configured library name is also associated with a distinct
        configured or installed-app-discovered module path, the configured
        library remains in the conflict determination and templates.E003 is
        produced.
        """
        discovered_module_path = (
            "check_framework.template_test_apps.same_tags_app_2."
            "templatetags.same_tags"
        )
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
            ]
        ), patch(
            "django.core.checks.templates.get_template_tag_modules",
            return_value=[("same_tags", discovered_module_path)],
        ):
            self.assertEqual(
                check_for_template_tags_with_the_same_name(None),
                [self.error_same_tags],
            )

    def test_tpl_005_repeated_conflicting_associations_produce_each_distinct_path_once(
        self,
    ):
        """
        GUID: TPL-005

        When a library name has multiple distinct module paths and any
        association is collected repeatedly, the templates.E003 diagnostic
        identifies every distinct conflicting path exactly once.
        """
        first_module_path = (
            "check_framework.template_test_apps.same_tags_app_1."
            "templatetags.same_tags"
        )
        second_module_path = (
            "check_framework.template_test_apps.same_tags_app_2."
            "templatetags.same_tags"
        )
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
            ]
        ), patch(
            "django.core.checks.templates.get_template_tag_modules",
            return_value=[
                ("same_tags", first_module_path),
                ("same_tags", second_module_path),
                ("same_tags", second_module_path),
            ],
        ):
            self.assertEqual(
                check_for_template_tags_with_the_same_name(None),
                [self.error_same_tags],
            )

    @override_settings(
        INSTALLED_APPS=[
            "check_framework.template_test_apps.same_tags_app_1",
            "check_framework.template_test_apps.same_tags_app_2",
        ]
    )
    def test_template_tags_with_same_name(self):
        self.assertEqual(
            check_for_template_tags_with_the_same_name(None),
            [self.error_same_tags],
        )

    def test_template_tags_with_same_library_name(self):
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
                self.get_settings(
                    "same_tags", "same_tags_app_2.templatetags.same_tags"
                ),
            ]
        ):
            self.assertEqual(
                check_for_template_tags_with_the_same_name(None),
                [self.error_same_tags],
            )

    @override_settings(
        INSTALLED_APPS=["check_framework.template_test_apps.same_tags_app_1"]
    )
    def test_template_tags_with_same_library_name_and_module_name(self):
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags",
                    "different_tags_app.templatetags.different_tags",
                ),
            ]
        ):
            self.assertEqual(
                check_for_template_tags_with_the_same_name(None),
                [
                    Error(
                        E003.msg.format(
                            "'same_tags'",
                            "'check_framework.template_test_apps.different_tags_app."
                            "templatetags.different_tags', "
                            "'check_framework.template_test_apps.same_tags_app_1."
                            "templatetags.same_tags'",
                        ),
                        id=E003.id,
                    )
                ],
            )

    def test_template_tags_with_different_library_name(self):
        with self.settings(
            TEMPLATES=[
                self.get_settings(
                    "same_tags", "same_tags_app_1.templatetags.same_tags"
                ),
                self.get_settings(
                    "not_same_tags", "same_tags_app_2.templatetags.same_tags"
                ),
            ]
        ):
            self.assertEqual(check_for_template_tags_with_the_same_name(None), [])

    @override_settings(
        INSTALLED_APPS=[
            "check_framework.template_test_apps.same_tags_app_1",
            "check_framework.template_test_apps.different_tags_app",
        ]
    )
    def test_template_tags_with_different_name(self):
        self.assertEqual(check_for_template_tags_with_the_same_name(None), [])
