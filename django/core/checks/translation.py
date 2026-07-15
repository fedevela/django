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

    # GEV-001, GEV-002 (pseudocode obligations):
    # INPUTS:
    #   LANGUAGE_CODE = settings.LANGUAGE_CODE
    #   AVAILABLE_TAGS = {tag for (tag, _name) in settings.LANGUAGES} ∪ {'en-us'}
    #   BASE_LANGUAGE = substring before the first '-' in LANGUAGE_CODE.
    # STATE/CONTROL:
    #   - First branch is exact-match membership for consistency.
    #   - Fallback branch only executes when exact match fails.
    #   - Non-passthrough path emits translation.E004.
    # DECISION FLOW:
    #   1) IF LANGUAGE_CODE is empty or malformed, skip this path and let
    #      check_setting_language_code report validation errors.
    #   2) IF LANGUAGE_CODE ∈ AVAILABLE_TAGS -> PASS (exact-match accepted).
    #      - This satisfies GEV-002-S1 and GEV-002-S2, including cases where
    #        LANGUAGES includes both 'es' and 'es-ar'.
    #      - Do NOT evaluate fallback only because of the presence of a base tag.
    #   3) ELSE:
    #      a) IF BASE_LANGUAGE != LANGUAGE_CODE AND BASE_LANGUAGE ∈ AVAILABLE_TAGS
    #         -> PASS (regional fallback by base language).
    #         - This satisfies GEV-001-S1/S2.
    #      b) OTHERWISE -> FAIL [E004] only.
    #   4) END.
    #
    # Handoff:
    #   - Returns [] (pass) when exact-match or fallback branch succeeds.
    #   - Returns [E004] only when neither branch can satisfy membership.

    language_code = settings.LANGUAGE_CODE
    if language_code in available_tags:
        # GEV-002: exact-match variant accepted directly (including 'es-ar').
        return []

    # GEV-001: allow regional LANGUAGE_CODE fallback to its base language
    # if the base language exists in LANGUAGES.
    # Do not reach this branch for GEV-002 exact-match hits.
    if language_code not in available_tags:
        base_language = language_code.split('-')[0]
        if base_language != language_code and base_language in available_tags:
            return []
        return [E004]
    return []
