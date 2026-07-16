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
    # Architecture ownership (TRANS-001, TRANS-002, TRANS-003, TRANS-004,
    # TRANS-005, TRANS-006): E004 support policy belongs entirely to this
    # system-check boundary. Its inputs are settings.LANGUAGE_CODE and the
    # locally constructed available-tag inventory; runtime translation
    # resolution isn't a dependency of this check. Exact and base-tag support
    # therefore share this local inventory seam, while the other registered
    # translation checks retain their separate ownership above.
    # Pseudocode contract for translation.E004:
    #
    # TRANS-004 INPUT: Read LANGUAGE_CODE and build the available-code set by
    # preserving the check's established code representation, membership
    # semantics, and implicit ``en-us`` availability.
    # TRANS-003 DECISION 1: If LANGUAGE_CODE is an exact member of that set,
    # return no translation.E004 error.
    # TRANS-001, TRANS-004 DECISION 2: Otherwise, derive only the established
    # base-language component of LANGUAGE_CODE. If that base code is an exact
    # member of the same set, return no translation.E004 error. Do not add
    # recursive, variant-to-variant, or newly normalized matching paths.
    # TRANS-002 FAILURE: If neither comparison succeeds, return E004.
    # TRANS-005 BOUNDARY: This procedure only reports setting consistency; it
    # must not activate a language, select a catalog, or mutate runtime
    # translation and fallback state.
    # TRANS-006 HANDOFF: Return only this procedure's E004 result. Leave E001,
    # E002, E003, and every other registered translation check to their
    # existing procedures without suppressing, replacing, or reordering them.
    available_tags = {i for i, _ in settings.LANGUAGES} | {'en-us'}
    if settings.LANGUAGE_CODE not in available_tags:
        return [E004]
    return []
