AUTO-001 — Manage script inclusion in StatReloader initial watched set
===================================================================

Purpose
-------

Place the deterministic requirement for ``AUTO-001`` into a stable structure:

``Given `python manage.py runserver`, the initial watcher snapshot for
``StatReloader`` must include the concrete launch script path used for
process start.`` 

Requirement-to-architecture map
------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Rationale
   * - ``AUTO-001``
     - Include the concrete launch script path used to start ``runserver`` in the
       initial watched-file stream.
     - ``django.utils.autoreload``
     - Keeps file-watcher correctness constrained to the current reloader
       boundary without changing reload mechanics.

Pressure decomposition
---------------------

*Ownership*
  - ``django.utils.autoreload`` owns the initial snapshot pipeline
    (``iter_modules_and_files`` → ``BaseReloader.watched_files`` →
    ``StatReloader.snapshot_files``).

*Boundary*
  - Command-line launch context (``sys.argv``/entry script) is an
    external boundary input.
  - Watcher internals are internal to the reloader boundary and must consume a
    normalized, absolute-path launch candidate.

*Contracts*
  - ``iter_modules_and_files(modules, extra_files)`` returns a ``frozenset`` of
    absolute ``Path`` values representing candidate watched files.
  - ``BaseReloader.watched_files(include_globs=True)`` yields absolute ``Path``
    values by composing module candidates, explicit reloader file adds, and glob
    expansions.
  - ``StatReloader.snapshot_files()`` consumes that stream and emits
    deduplicated ``(Path, mtime)``, which is the first snapshot contract boundary.

*Dependency direction*
  - Process launch context flows inward: CLI entry context -> watcher candidate
    stream -> snapshot output.
  - No dependency changes from file-system watcher backends; snapshot scope is
    constrained to caller-provided path candidates.

Integration seam plan
---------------------

1. Add a dedicated, ownership-local seam under ``django.utils.autoreload`` for a
   launch-script path adapter:

   - Input: resolved launch script path candidate derived from reloader startup
     context.
   - Output: absolute ``Path`` candidate guaranteed to participate in
     ``watched_files`` stream composition before snapshot diff.

2. Keep the seam within the reloader stack:

   - Primary owner: ``BaseReloader`` for stream assembly.
   - Initial verifier home: ``tests/utils_tests/test_autoreload.py``
     ``StatReloaderTraceabilityTests``.

3. Do not modify watcher backends or reload signaling behavior outside this
   pipeline.

Concrete artifact mapping
-------------------------

* Changed architecture artifact:
  - ``docs/architecture/AUTO-001-manage-py-watcher-architecture.rst`` (this file)

* Traceability references:
  - ``django/utils/autoreload.py``
    ``iter_modules_and_files`` / ``BaseReloader.watched_files`` /
    ``StatReloader.snapshot_files``
  - ``tests/utils_tests/test_autoreload.py``
    ``StatReloaderTraceabilityTests.test_auto_001_initial_watch_list_includes_manage_py_launch_path``

Completion notes
---------------

* All traced obligations map to a concrete file path and ownership boundary.
* Structural direction is explicit: launch context is an upstream input; all watcher
  snapshot behavior remains in ``django.utils.autoreload``.
* Readiness for implementation: high, with one seam to instantiate and wire in next phase.
