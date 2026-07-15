AUTO-003 - Manage path canonicalization in watcher snapshot
==========================================================

Purpose
-------

Place the deterministic requirement for ``AUTO-003`` into stable structure:

``Given `runserver` is started via any valid `manage.py` launch form (absolute,
relative, symlinked, or subdirectory launch), the watched entry must be the
single canonical absolute real path to the target file.`` 

Requirement
-----------

Canonicalized launch path must be determined before watcher snapshot assembly and
cannot bypass the reloader module boundary.

Requirement-to-architecture map
-------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Rationale
   * - ``AUTO-003``
     - Convert launch-script inputs to one canonical absolute real path and add
       exactly one manage.py watch entry when valid.
     - ``django.utils.autoreload`` (`get_manage_py_path` and
       ``StatReloader.__init__``)
     - Keeps path normalization and watcher seeding inside reloader ownership;
       avoids leaking CLI normalization into restart orchestration.

Pressure decomposition
---------------------

*Ownership*
  - ``django.utils.autoreload.get_manage_py_path`` owns launch-script normalization
    and eligibility checks.
  - ``django.utils.autoreload.StatReloader.__init__`` owns the startup watch
    seeding decision for manage.py.
  - ``django.utils.autoreload.BaseReloader.watch_file`` owns invariant enforcement
    for absolute watcher entries.
  - ``tests.utils_tests.test_autoreload.StatReloaderTraceabilityTests`` owns
    coverage for launch-form permutations.

*Boundary*
  - ``sys.argv`` is an external execution boundary input to the reloader module.
  - Path normalization to a canonical filesystem location is an internal boundary
    contract produced by ``get_manage_py_path`` before watcher registration.
  - ``BaseReloader.watched_files`` and downstream snapshot logic consume only
    normalized candidates.

*Contracts*
  - ``get_manage_py_path() -> Optional[Path]``
    - Input: launch context values in ``sys.argv``.
    - Output: either ``Path`` where
      - file name is exactly ``manage.py``
      - path is absolute
      - symlink/relative tokens are resolved to a real filesystem path
      - file exists
      otherwise ``None``.
  - ``StatReloader.__init__() -> None``
    - Calls ``get_manage_py_path`` once on construction.
    - If ``None``, contributes no extra manage.py watch entry.
    - If ``Path``, invokes ``self.watch_file`` exactly once with that path.
  - ``watch_file(path: Path) -> None``
    - Requires absolute ``Path`` input.
    - Adds to ``extra_files`` set for snapshot participation.

*Dependency direction*
  - CLI launch context (``sys.argv``) -> ``get_manage_py_path`` -> ``StatReloader.__init__`` ->
    ``watch_file`` -> ``BaseReloader.extra_files`` -> ``BaseReloader.watched_files`` ->
    snapshot stream.
  - No upstream dependency is introduced from watcher internals to process restart
    logic; canonicalization is local to the reloader startup edge.

Integration seam plan
---------------------

1. Preserve and implement ownership at function level:
   - ``get_manage_py_path`` performs only launch-script normalization and
     validity filtering.
   - ``StatReloader.__init__`` is the single downstream consumer for that
     normalized value.

2. Enforce one-way registration semantics:
   - At startup, register one entry when and only when ``get_manage_py_path``
     returns a validated canonical path.
   - Avoid duplicate registration by using set semantics in
     ``BaseReloader.extra_files`` and one invocation site.

3. Keep path invariants at module boundary:
   - Normalize with ``Path.resolve()`` in ``get_manage_py_path``.
   - Preserve all canonicalization policy in one owning module to minimize
     coupling.

Concrete architecture artifact mapping
-------------------------------------

* Changed architecture artifact:
  - ``docs/architecture/AUTO-003-manage-py-canonical-absolute-realpath-architecture.rst`` (this file)

* Runtime contract loci:
  - ``django/utils/autoreload.py``
    - ``get_manage_py_path``
    - ``StatReloader.__init__``
    - ``BaseReloader.watch_file``

* Traceability loci:
  - ``tests/utils_tests/test_autoreload.py``
    ``StatReloaderTraceabilityTests``

    - ``test_auto_003_watch_entry_for_manage_py_absolute_launch_path_is_canonical_absolute_realpath``
    - ``test_auto_003_watch_entry_for_manage_py_relative_launch_path_is_canonical_absolute_realpath``
    - ``test_auto_003_watch_entry_for_manage_py_symlink_launch_path_is_canonical_absolute_realpath``
    - ``test_auto_003_watch_entry_for_manage_py_subdirectory_launch_path_is_canonical_absolute_realpath``

Completion notes
---------------

* ``AUTO-003`` has explicit ownership, boundary, contract, dependency, and seam
  placement.
* Structural placement is ready for implementation and traceability continuity:
  canonicalization is bound to ``django.utils.autoreload`` and watch-seed entry
  is routed through ``StatReloader.__init__``.
