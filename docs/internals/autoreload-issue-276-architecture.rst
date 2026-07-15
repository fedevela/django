Issue #276 — Reject malformed-path substitutions in module file resolution
=======================================================================

Canonical requirement
--------------------

- ARL-004 [RED]: A malformed path candidate must never be rewritten into
  alternate valid-looking paths (parent/normalized/truncated variants) during
  module file resolution.

Requirement-to-architecture map
-------------------------------

- ARL-004.1 (strict omit semantics): maps to
  ``django.utils.autoreload.iter_modules_and_files()`` where each raw candidate
  is resolved independently and ``ValueError("embedded null byte")`` transitions
  to terminal skip.
- ARL-004.2 (no fallback generation): maps to the same loop and transition
  point in ``iter_modules_and_files()``, where no derivation adapters are
  introduced.
- ARL-004.3 (identity across ticks): maps to the re-entry seam between
  ``StatReloader.tick()`` and ``StatReloader.snapshot_files()`` and the call into
  ``BaseReloader.watched_files()/iter_all_python_module_files()``, which must
  reconsume the raw candidate set on each cycle.

Placement and ownership decisions
--------------------------------

- ``django/utils/autoreload.py`` owns candidate resolution.
  - ``iter_modules_and_files(modules, extra_files)`` remains the only owner of
    raw filename-to-Path candidate transformation.
  - It owns the malformed-path branch decision for that candidate.
- ``django/utils/autoreload.py`` owns per-cycle watch enumeration.
  - ``BaseReloader.watched_files()`` owns composition of watched paths for the
    cycle, with no extra-path synthesis.
  - ``StatReloader.snapshot_files()`` owns per-tick materialization of
    stat-able files from current watched inputs.
- Test scaffolding in ``tests/utils_tests/test_autoreload.py`` owns ARL-004
  observable obligations through placeholder/traceability tests until behavior
  validation is implemented.

Contract and boundary artifacts
-------------------------------

- Candidate boundary
  - Input contract: iterable of raw candidates (`str` and filesystem-like module
    origins) entering ``iter_modules_and_files()``.
  - Output contract: emit only concrete resolved ``Path`` values for successful
    candidates.
  - Malformed-path contract: ``ValueError("embedded null byte")`` must map to
    omit + continue (no substitution, no parent walk, no normalization fallback,
    no truncation derivative).
- Cycle boundary
  - Tick contract: each execution of ``snapshot_files()`` consumes current output
    of ``watched_files()`` for that cycle.
  - Re-entry contract: only raw candidate identities can re-enter future cycles;
    no derived substitutes are persisted across tick boundaries.

Dependency-direction notes
-------------------------

Current direction remains:

``run_with_reloader`` -> ``BaseReloader`` -> ``StatReloader`` ->
``BaseReloader.watched_files`` -> ``iter_all_python_module_files`` ->
``iter_modules_and_files``.

This keeps ``iter_modules_and_files`` as a pure candidate-resolution boundary that
does not depend on prior-cycle substitute history.

Integration seam skeleton
-------------------------

1. Candidate intake seam (required)
   - ``iter_modules_and_files()`` is the only seam that resolves raw candidate
     candidates into filesystem ``Path`` values for this flow.
2. Tick re-evaluation seam (required)
   - ``StatReloader.tick()`` should rely on ``snapshot_files()`` output each cycle;
     no synthetic candidate cache for malformed entries.
3. Recovery seam (required)
   - Malformed candidates are reprocessed as their original raw form when they
     reappear in subsequent cycles.

Traceability notes
------------------

- Verification map anchor (existing): ``ARL_275_VERIFICATION_MAP["ARL-004"]`` in
  ``tests/utils_tests/test_autoreload.py``.
- New architecture artifact added: ``docs/internals/autoreload-issue-276-architecture.rst``.

