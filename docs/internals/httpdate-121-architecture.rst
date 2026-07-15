HTTPDATE-121 Architecture Artifact (Yesod)
=========================================

:Issue: #121
:Canonical Requirements: HTTPDATE-001, HTTPDATE-002, HTTPDATE-005
:Scope: RFC 850 two-digit year handling in ``django.utils.http.parse_http_date``

Requirement-to-architecture mapping
----------------------------------

- HTTPDATE-001
  - Pressure: algorithmic ownership and placement
  - Architecture locus: ``parse_http_date`` RFC850 branch (``if year < 100:``)
  - Rationale: century inference is parsing-normalization responsibility, not shared
    with upstream consumers.

- HTTPDATE-002
  - Pressure: boundary condition ownership
  - Architecture locus: same RFC850 branch
  - Rationale: strict ``> 50`` offset check is a parse-rule control point and must be
    encoded in the same inference block.

- HTTPDATE-005
  - Pressure: dependency direction and data-driven behavior
  - Architecture locus: same RFC850 branch
  - Rationale: hardcoded century split constants must not be data inputs to this path;
    the year decision must be computed from runtime year ``C``.

Module and file placement decisions
-----------------------------------

- Parser boundary
  - Keep logic inside ``django/utils/http.py`` within ``parse_http_date``.
  - Do not move or split date parsing by format into new public modules.
- Ownership
  - ``parse_http_date`` retains ownership of:
    - RFC1123/RFC850/ASCTIME format selection
    - field extraction and conversion
    - validation and failure mapping to ``ValueError``
  - RFC850 year inference remains owned by the two-digit-year branch in the same function.

Structural contracts and dependencies
-----------------------------------

- Existing function contract stays unchanged:
  - Input: RFC date string
  - Output: seconds since epoch as ``int`` or ``ValueError``
- New inferred contract in RFC850 two-digit-year branch:
  - Input: parsed two-digit ``year`` and runtime current year ``C``
  - Mapping: ``century_base = C - (C % 100)``, ``candidate = century_base + year``
  - Rule: if ``candidate - C > 50`` then ``year = candidate - 100`` else ``year = candidate``
  - Boundary: ``candidate - C == 50`` remains in current century
  - Invariance: all other parsed fields remain unchanged

Dependency direction notes
-------------------------

- Direction remains one-way from parser internals to standard library helpers:
  - ``parse_http_date`` -> ``datetime.date.today().year`` for current year input
  - ``parse_http_date`` -> ``calendar.timegm`` for epoch conversion
- No new imports or public API dependencies are introduced.
- No changes outside ``django.utils.http`` call sites are required.

Integration seam skeleton
-------------------------

- RFC850 two-digit-year inference is a bounded seam with one entry/exit point in
  the existing ``year < 100`` branch.
- For later implementation, this seam can be refactored into a private helper
  without changing the external parser contract or public APIs.
- Existing traceability tests already point to dedicated IDs in
  ``tests/utils_tests/test_http.py``; no behavioral assertions are required in
  this architecture phase.

Readiness assessment
--------------------

- All traced obligations have a concrete locus in ``django.utils.http.parse_http_date``.
- The two-digit-year century rule is architecture-placed as a controlled boundary in
  the parser.
- One concrete architecture artifact has been added:
  - ``docs/internals/httpdate-121-architecture.rst``
