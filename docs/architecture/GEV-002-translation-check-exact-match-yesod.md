# GEV-002 Architecture: translation exact-match acceptance for supported variants

## Completion gate tracking

- Status: ready for implementation.
- Structural artifact updated in this phase:
  - `docs/architecture/GEV-002-translation-check-exact-match-yesod.md`
- Traceability integrity: each architectural change below maps to `GUID: GEV-002` and scenario references `GEV-002-S1`/`GEV-002-S2`.
- Runtime behavior: not modified in this phase.

## Requirement-to-architecture pressures

- `GUID: GEV-002` / `GEV-002-S1` pressure: ownership boundary and control-flow order must guarantee exact-match acceptance before any fallback resolution.
  - Canonical effect: `LANGUAGE_CODE` in `available_tags` is a terminal pass path and cannot produce `translation.E004`.
- `GUID: GEV-002` / `GEV-002-S2` pressure: integration seam with base-language fallback must not shadow exact-match.
  - Canonical effect: `LANGUAGE_CODE='es-ar'` is accepted from explicit membership even when `'es'` is also present in `LANGUAGE_CODE`-equivalent alternatives.
- `GEV-002-S2` seam pressure: test and production artifacts must express the same ownership point (`check_language_settings_consistent`) so future implementation remains coupled to requirement intent.

## File/module placement decisions

- Owning production module: `django/core/checks/translation.py`
  - Entry point: `check_language_settings_consistent`
  - Registry seam: decorated with `@register(Tags.translation)`; function is in the check framework boundary.
- Traceability/Test module: `tests/check_framework/test_translation_gev002.py`
  - Scenarios:
    - `test_gev_002_exact_match_for_supported_variant_stays_passed`
    - `test_gev_002_variant_with_base_language_skips_fallback_validation_path`
- Canonical dependency direction: tests exercise behavior; production module owns policy and emits checks.

## Ownership boundaries

- Boundary A (syntax validation): `check_setting_language_code`
  - Responsibility: validate format of `settings.LANGUAGE_CODE`.
  - Dependency: `language_code_re` from `django.utils.translation.trans_real`.
- Boundary B (set consistency policy): `check_language_settings_consistent`
  - Responsibility: enforce inclusion/fallback policy between `LANGUAGE_CODE` and `LANGUAGES`.
  - Responsibility includes:
    - Constructing `available_tags`.
    - Short-circuit pass branch for exact membership.
    - Fallback branch for base-language resolution.
    - Emitting `[E004]` only on terminal failure.
- Boundary C (traceability): `tests/check_framework/test_translation_gev002.py`
  - Responsibility: preserve scenario intent (`GEV-002-S1`, `GEV-002-S2`) for future concrete assertions.

## Interface / contract artifacts

- `check_language_settings_consistent(app_configs, **kwargs) -> list[Error]`
- Input contract:
  - Reads `settings.LANGUAGE_CODE` and `settings.LANGUAGES`.
  - Expects language entries as iterable tags from `LANGUAGES`.
- Output contract:
  - Empty list: consistency accepted.
  - One-element list `[E004]` only when no explicit variant or accepted base fallback exists.
- Cross-function contract:
- `check_setting_language_code` should have already guarded invalid `LANGUAGE_CODE` syntax before this function determines consistency outcome.
- Cross-data contract:
  - `available_tags` is treated as a set of canonicalized locale tags plus `'en-us'`.

## Dependency-direction notes

- `LANGUAGES` and `LANGUAGE_CODE` flow:
  - `settings` -> `translation.py` check function.
- Fallback relation flows:
  - explicit exact-match path (pass) → terminate.
  - else base-language branch (pass) → terminate.
  - else fallback failure -> `[E004]`.
- Non-regression direction:
  - `check_language_settings_consistent` must not depend on test placeholders, and test placeholders must not alter production control flow.

## Integration seam skeletons

- Integration node: Django check framework registration seam
  - Function remains in `Tags.translation` registration stream.
- Integration node: settings configuration seam
  - Input provider: `django.conf.settings`.
  - Required stable interface: iterable `settings.LANGUAGES` and string `settings.LANGUAGE_CODE`.
- Integration node: error aggregation seam
  - Emitted error object is `E004` from the same module constant namespace.
- Handoff seam after architecture phase:
  - Maintain this control flow in implementation handoff and add concrete assertions in tests without changing module boundaries.

## Structural placeholders

- No new runtime classes/types/interfaces are added in this phase.
- Pseudocode-level decision order remains the control contract:
  1. exact match on `LANGUAGE_CODE in available_tags`.
  2. base language fallback only when exact match misses.
  3. fail with `[E004]` only otherwise.
- Placeholder tests and comments are accepted as traceability scaffolds until concrete assertions are implemented.

## Requirement-to-architecture trace map

- `GUID: GEV-002` → `django/core/checks/translation.py` (`check_language_settings_consistent`)
  - Satisfies the exact-match acceptance boundary and failure gate.
- `GEV-002-S1` → same function, exact-match branch.
- `GEV-002-S2` → same function and branch ordering; verifies exact match is decisive over fallback presence.
- `GEV-002-S1` traceability scaffold → `tests/check_framework/test_translation_gev002.py::test_gev_002_exact_match_for_supported_variant_stays_passed`
- `GEV-002-S2` traceability scaffold → `tests/check_framework/test_translation_gev002.py::test_gev_002_variant_with_base_language_skips_fallback_validation_path`
