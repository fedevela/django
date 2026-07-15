# GEV-001 Architectural placement: translation language-code consistency

## Requirement-to-architecture mapping

- `GUID: GEV-001`: accept `LANGUAGE_CODE` regional fallback when the base language exists in `LANGUAGES`.
- Scenario `GEV-001-S1` (`de-at` / `de`): route to consistency seam in `django.core.checks.translation.check_language_settings_consistent`.
- Scenario `GEV-001-S2` (`fr-ca` / `fr`): same route as S1.

## Ownership decisions

- owning module: `django/core/checks/translation.py`
  - function: `check_language_settings_consistent`
  - owns the consistency policy between `LANGUAGE_CODE` and `LANGUAGES`.
- test ownership: `tests/check_framework/test_translation.py`
  - functions:
    - `test_gev_001_regional_language_code_with_base_language_present_no_e004`
    - `test_gev_001_french_regional_code_with_base_language_present_no_e004`

## Boundary definitions

- validation boundary:
  - `check_setting_language_code` remains responsible for syntax/format validation of `LANGUAGE_CODE`.
  - `check_language_settings_consistent` owns semantic membership decisions only.
- catalog boundary:
  - accepted source for canonical membership is `settings.LANGUAGES`, augmented with `'en-us'` fallback via existing implementation behavior.

## Interface and contract

- module interface: `check_language_settings_consistent(app_configs, **kwargs) -> list[Error]`.
- semantic contract for this obligation:
  - must return `[]` when `LANGUAGE_CODE` exact-match exists in available tags.
  - must return `[]` when `LANGUAGE_CODE` is regional and base language (before `-`) exists in available tags.
  - must return `[E004]` only when neither exact-match nor base-language fallback applies.

## Dependency-direction notes

- upstream settings producer: `django.conf.settings` → `LANGUAGE_CODE`, `LANGUAGES`.
- check layer consumers: call sites via Django checks framework (`@register(Tags.translation)`).
- error emission is leaf-level effect from this check to check framework reporting.

## Integration seams

- seam A: check discovery via `@register(Tags.translation)` keeps behavior isolated to the checks registry.
- seam B: acceptance tests assert contract without coupling to translation catalog loading.
- seam C: parser/format layer remains separated (`language_code_re`) in existing validation checks.

## Completion status

- structural artifacts updated: yes (`docs/architecture/GEV-001-translation-check-yesod.md`).
- traced obligations mapped to repository loci: yes.
- implementation-ready boundary/ownership/contract set: yes.
