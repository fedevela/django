from django.conf import settings
from django.utils.translation.trans_real import language_code_re

from . import Error, Tags, register

E001 = Error(
    'You have provided an invalid value for the LANGUAGE_CODE setting: {!r}.',
    id='translation.E001',
)

E002 = Error(
    'You have provided an invalid language code in the LANGUAGES setting: {!r}.',
    id='translation.E002',
)

E003 = Error(
    'You have provided an invalid language code in the LANGUAGES_BIDI setting: {!r}.',
    id='translation.E003',
)

E004 = Error(
    'You have provided a value for the LANGUAGE_CODE setting that is not in '
    'the LANGUAGES setting.',
    id='translation.E004',
)


@register(Tags.translation)
def check_setting_language_code(app_configs, **kwargs):
    """Error if LANGUAGE_CODE setting is invalid."""
    tag = settings.LANGUAGE_CODE
    if not isinstance(tag, str) or not language_code_re.match(tag):
        return [Error(E001.msg.format(tag), id=E001.id)]
    return []


@register(Tags.translation)
def check_setting_languages(app_configs, **kwargs):
    """Error if LANGUAGES setting is invalid."""
    return [
        Error(E002.msg.format(tag), id=E002.id)
        for tag, _ in settings.LANGUAGES if not isinstance(tag, str) or not language_code_re.match(tag)
    ]


@register(Tags.translation)
def check_setting_languages_bidi(app_configs, **kwargs):
    """Error if LANGUAGES_BIDI setting is invalid."""
    return [
        Error(E003.msg.format(tag), id=E003.id)
        for tag in settings.LANGUAGES_BIDI if not isinstance(tag, str) or not language_code_re.match(tag)
    ]


@register(Tags.translation)
def check_language_settings_consistent(app_configs, **kwargs):
    """Error if language settings are not consistent with each other."""
    available_tags = {i for i, _ in settings.LANGUAGES} | {'en-us'}

    # GEV-001 (pseudocode obligation):
    # INPUT:
    #   LANGUAGE_CODE = settings.LANGUAGE_CODE
    #   AVAILABLE_TAGS = {tag for (tag, _name) in settings.LANGUAGES} ∪ {'en-us'}
    #   BASE_LANGUAGE = substring before the first '-' in LANGUAGE_CODE.
    # DECISION FLOW:
    #   1) IF LANGUAGE_CODE is empty or malformed, do not consume this pseudocode path;
    #      defer to `check_setting_language_code` for validation errors.
    #   2) IF LANGUAGE_CODE is in AVAILABLE_TAGS -> consistent (pass).
    #   3) IF LANGUAGE_CODE is not in AVAILABLE_TAGS:
    #        a) IF BASE_LANGUAGE ≠ LANGUAGE_CODE AND BASE_LANGUAGE is in AVAILABLE_TAGS
    #           -> accept as regional fallback (pass), do not emit E004.
    #        b) OTHERWISE -> emit [E004].
    #   4) ELSE -> pass.
    # FAILURE PATH:
    #   - only non-passthrough case is branch 3.b, which returns [E004].
    # SCENARIOS:
    #   - S1: LANGUAGE_CODE='de-at', LANGUAGES=[('de','German')] => base 'de' present -> no E004.
    #   - S2: LANGUAGE_CODE='fr-ca', LANGUAGES=[('fr','French')] => base 'fr' present -> no E004.

    if settings.LANGUAGE_CODE not in available_tags:
        return [E004]
    return []
