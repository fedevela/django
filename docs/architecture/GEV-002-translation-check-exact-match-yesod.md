# GEV-002 Architectural placement: exact-match variants in translation checks

## Requirement-to-architecture mapping

- `GUID: GEV-002`: accept `LANGUAGE_CODE` exactly when it appears in `LANGUAGES`, including regional variants like `es-ar`, and do not route that case through fallback-only failure paths.
- Scenario `GEV-002-S1`: `LANGUAGE_CODE='es-ar'` and `LANGUAGES` contains `es-ar`: the check must treat this as consistent and not emit `translation.E004`.
- Scenario `GEV-002-S2`: `LANGUAGE_CODE='es-ar'` and `LANGUAGES` contains both `es` and `es-ar`: explicit variant membership must satisfy consistency even when a base language is also present.

## Ownership decisions

- owning module: `django/core/checks/translation.py`
  - function: `check_language_settings_consistent`
- traceability owner: `tests/check_framework/test_translation_gev002.py`
  - function:
    - `test_gev_002_exact_match_for_supported_variant_stays_passed`
    - `test_gev_002_variant_with_base_language_skips_fallback_validation_path`

## Boundary definitions

- check boundary:
  - `check_setting_language_code` validates syntax.
  - `check_language_settings_consistent` owns inclusion and fallback-consistency policy.
- traceability boundary:
  - these obligations are expressed here as explicit, non-assertive placeholders to avoid runtime behavior changes in this phase.

## Completion status

- structural artifacts updated: yes (`docs/architecture/GEV-002-translation-check-exact-match-yesod.md`).
- traced obligations mapped to repository loci: yes.
- behavioral assertions avoided in this phase: yes.
