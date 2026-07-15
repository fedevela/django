Issue #275 — Resilient autoreload module iteration across ticks
=============================================================

Canonical requirements
---------------------

- ARL-001: malformed candidate resolution (`ValueError("embedded null byte")`) must be contained locally and not abort scan.
- ARL-002: on one malformed candidate, scan must continue and include all other candidates.
- ARL-003: periodic `snapshot_files()` runs must remain functional after intermittent failures.
- ARL-007: malformed candidates must be retried deterministically; no synthetic alternate paths.

Requirement-to-architecture map
-------------------------------

``iter_modules_and_files()`` is the owning boundary for candidate intake and
normalization.

- ARL-001 maps to the per-item path-resolution contract in
  ``django/utils/autoreload.py``: each candidate is resolved independently and
  `ValueError("embedded null byte")` is translated into "skip only this
  candidate".
- ARL-002 maps to the same loop in ``iter_modules_and_files()``: handling happens
  inside the loop, never outside it, so every non-failing candidate keeps
  progressing through the current cycle.
- ARL-003 maps to snapshot ownership in ``StatReloader.snapshot_files()`` and its
  per-tick call chain: each tick invokes ``self.watched_files()`` fresh and does
  not keep malformed-candidate state that could starve later resolutions.
- ARL-007 maps to the recomputation boundary between
  ``iter_modules_and_files()`` and ``snapshot_files()``: no synthetic path
  substitution is introduced in this seam; the same raw candidate input is allowed
  to be re-evaluated on subsequent ticks.

Placement and boundaries
------------------------

- ``django/utils/autoreload.py``
  owns the resilient scan boundary.
  - ``iter_modules_and_files(modules, extra_files)`` owns raw module/error path
    candidates and returns a stable ``frozenset(Path)`` snapshot of resolvable files.
  - It must remain a pure transformation boundary with no persistence of
    candidate-failure history.
- ``StatReloader.snapshot_files()`` owns per-tick file enumeration.
  - It must treat ``self.watched_files()`` as an authoritative input for the
    current cycle.
  - It should retain dedupe per-tick state only, not per-path failure memory.

Interface/contract notes
------------------------

- Candidate input contract
  - Input type: sequence of module-like and/or string-like path identifiers.
  - Failing path contract: a candidate that raises `ValueError("embedded null byte")`
    on `Path(...).resolve(strict=True).absolute()` is treated as "omit this
    cycle".
- Output contract for ``iter_modules_and_files``
  - Output type: ``frozenset(Path)`` containing only successfully resolved paths.
  - Error contract: swallow only the targeted embedded-null failure path and
    ``FileNotFoundError``, continue the loop.
- Tick contract for ``snapshot_files``
  - Input: current output of ``self.watched_files()`` for that tick.
  - Output: generator of `(filepath, mtime)` pairs for files currently stat-able.
  - Recovery contract: reattempt all raw candidates each cycle; no alternate path
    variants are introduced.

Dependency direction
--------------------

- ``run_with_reloader`` / ``start_django`` -> ``BaseReloader`` -> ``StatReloader``.
- ``StatReloader.snapshot_files`` depends on ``BaseReloader.watched_files``.
- ``BaseReloader.watched_files`` depends on ``iter_all_python_module_files``.
- ``iter_all_python_module_files`` depends on ``iter_modules_and_files``.
- ``iter_modules_and_files`` depends only on module metadata and string path
  inputs; it must not depend on tick state.

Integration-seam skeleton (no behavior changes)
-----------------------------------------------

1. Candidate collection seam
   - ``iter_modules_and_files()`` remains the only place that resolves raw
     candidate strings into ``Path`` objects for this issue.
2. Tick execution seam
   - ``StatReloader.snapshot_files()`` remains the place that materializes per-tick
     `(path, mtime)` observations.
3. Re-entry seam
   - no persistence of rejected raw candidate substitutions; failures are naturally
     re-entered via the next `iter_modules_and_files()` cycle.

Readiness note
--------------

- Structural artifacts updated:
  - Added architecture artifact:
    ``docs/internals/autoreload-issue-275-architecture.rst``
  - Existing traceability artifact remains:
    ``tests/utils_tests/test_autoreload.py`` with ``ARL_275_VERIFICATION_MAP`` and
    ARL placeholder tests.
- Each requirement has at least one mapped architecture locus; placement,
  ownership, and boundaries are explicit and deterministic for implementation.
