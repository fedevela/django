from django.core.checks import Error
from django.core.checks.translation import check_language_settings_consistent
from django.test import SimpleTestCase


class TranslationCheckExactMatchTraceabilityTests(SimpleTestCase):
    def test_gev_002_exact_match_for_supported_variant_stays_passed(self):
        # GEV-002-S1:
        # Given LANGUAGE_CODE='es-ar' and LANGUAGES contains ('es-ar', ...)
        # When the translation consistency check is run
        # Then no translation.E004 is returned (explicit variant path is accepted).
        msg = (
            'You have provided a value for the LANGUAGE_CODE setting that is '
            'not in the LANGUAGES setting.'
        )
        with self.settings(
            LANGUAGE_CODE='es-ar',
            LANGUAGES=[('es-ar', 'Spanish (Argentina)'), ('en', 'English')],
        ):
            errors = check_language_settings_consistent(None)
            self.assertEqual(errors, [])
            self.assertNotIn(
                Error(msg, id='translation.E004'),
                errors,
            )

    def test_gev_002_variant_with_base_language_skips_fallback_validation_path(self):
        # GEV-002-S2:
        # Given LANGUAGE_CODE='es-ar' and LANGUAGES contains ('es', ...) and ('es-ar', ...)
        # When the translation consistency check is run
        # Then the check remains in the exact variant acceptance path.
        msg = (
            'You have provided a value for the LANGUAGE_CODE setting that is '
            'not in the LANGUAGES setting.'
        )
        with self.settings(
            LANGUAGE_CODE='es-ar',
            LANGUAGES=[('es', 'Spanish'), ('es-ar', 'Spanish (Argentina)')],
        ):
            errors = check_language_settings_consistent(None)
            self.assertEqual(errors, [])
            self.assertNotIn(
                Error(msg, id='translation.E004'),
                errors,
            )
