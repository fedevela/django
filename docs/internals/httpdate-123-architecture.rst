HTTPDATE-123 Architecture Artifact (Yesod)
=========================================

:Issue: #123
:Canonical Requirements: HTTPDATE-004
:Scope: Preserve malformed/unsupported input failure contracts so two-digit-year remap never turns invalid RFC 850-like text into a valid timestamp.

Requirement-to-architecture map
-------------------------------

- HTTPDATE-004 maps to `django.utils.http.parse_http_date` as the primary parse boundary and `django.utils.http.parse_http_date_safe` as the caller-facing contract boundary.
- The obligation is split into two seams:
  - Parse-seam: strict branch selection and terminal failure in `parse_http_date`.
  - Safety-seam: `parse_http_date_safe` remains a pure exception-to-`None` adapter and does not add recovery logic.

File and module placement decisions
----------------------------------

- Core parsing logic remains in `django/utils/http.py`.
- Invalid-input decision logic is owned inside `parse_http_date`; callers must not retry or reinterpret parse failures.
- No new modules are introduced because existing boundaries already isolate parser, remap gate, and caller adapter.

Ownership and boundary model
----------------------------

- `parse_http_date` owns:
  - Input format matching order (`RFC1123_DATE`, `RFC850_DATE`, `ASCTIME_DATE`).
  - Branch-local field extraction and conversion.
  - Terminal parse-failure ownership when no pattern matches.
- `parse_http_date` does not own fallback recovery outside RFC850 two-digit-year inference.
- `parse_http_date_safe` owns only:
  - Success return path from `parse_http_date`.
  - Exception absorption and `None` return.
  - No invocation of additional reparsing paths.

Dependency-direction notes
-------------------------

- Direction stays one-way from request handling to parser internals:
  - `parse_http_date` receives raw date text and emits either `int` epoch seconds or raises `ValueError`.
  - `parse_http_date_safe` consumes only that contract and translates exceptions into `None`.
- No new runtime dependencies are added; existing dependencies remain:
  - `datetime.date.today` (existing RFC850 two-digit-year logic gate context).
  - `calendar.timegm` (existing UTC conversion).

Integration-seam skeletons
--------------------------

- Harden the malformed-input seam with explicit guard points:
  - `if`/`else` branch that sets `is_rfc850` and `year_is_two_digits` remains the gate before any remap operation.
  - A negative parse result path that never returns to matching/remapping steps.
- Preserve exception path behavior in the `except` block as the explicit seam from parse failure to caller contract translation.

Requirement verification linkage
-------------------------------

- `tests/utils_tests/test_http.py::HttpDateMalformedInputTraceabilityTests` remains the implementation-ready verification locus for this requirement.
- Existing map entry:
  - `HTTPDATE_121_TRACEABILITY_MAP["HTTPDATE-004"]` references:
    - `HttpDateMalformedInputTraceabilityTests.test_httpdate_004_malformed_input_missing_required_tokens_stays_none`
    - `HttpDateMalformedInputTraceabilityTests.test_httpdate_004_invalid_rfc850_syntax_remains_none_without_century_recovery`
    - `HttpDateMalformedInputTraceabilityTests.test_httpdate_004_numeric_suffix_non_date_remains_none_no_fallback`

Readiness assessment
--------------------

- `HTTPDATE-004` has stable architectural placement in parser ownership and contract boundaries.
- There is a dedicated architecture artifact describing boundary ownership and failure-direction constraints without adding new parser behavior.
