AUTO-004 - Preserve existing watched paths while adding manage.py
===============================================================

Purpose
-------

Map `AUTO-004` to structure so watcher augmentation is additive and never
destructive:

- preserve all previously discovered modules, glob expansions, and explicit file
  entries
- add only one resolved ``manage.py`` watch entry when launch context is
  ``runserver``

Requirement
-----------

When ``python manage.py runserver`` starts with a non-empty watch set, adding
``manage.py`` must augment the existing collection rather than replace it.
`modules`, `globs`, and existing explicit `files` remain unchanged, and no
ordering guarantees are required beyond presence.

Requirement-to-architecture map
-------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Rationale
   * - ``AUTO-004``
     - Preserve previously discovered watch-source collections while adding one
       launch-script file.
     - ``django.utils.autoreload``
     - Prevents regression where bootstrap augmentation can remove baseline
       coverage used by reload detection.

Pressure decomposition
---------------------

*Ownership*
  - ``django.utils.autoreload.StatReloader.__init__`` owns startup augmentation
    for runserver launch-path seeding.
  - ``django.utils.autoreload.BaseReloader.watch_file`` owns invariant enforcement
    for explicit-file storage (`extra_files` set union behavior).
  - ``django.utils.autoreload.BaseReloader.watched_files`` owns composition of
    watched modules, explicit files, and globs as a single additive stream.
  - ``django.utils.autoreload.StatReloader.snapshot_files`` owns snapshot
    materialization policy (dedupe and stat-read of the composed stream).
  - ``tests.utils_tests.test_autoreload.StatReloaderTraceabilityTests`` owns
    requirement verification.

*Boundary*
  - ``sys.argv`` is an external launch boundary feeding ``get_manage_py_path``.
  - ``extra_files``, ``directory_globs``, and module snapshots must remain
    immutable collections for read during augmentation.
  - ``snapshot_files`` is the downstream boundary where transient missing-file
    absence is translated to skip; not a boundary for deterministic removals.

*Contracts*

  - ``watch_file(path: Path) -> None``
    - Input: absolute ``Path``.
    - Effect: insert/update membership in ``extra_files`` without clearing
      existing entries.
  - ``watched_files(include_globs=True) -> Iterable[Path]``
    - Emits module-derived files, existing ``extra_files`` contents, then glob
      expansion results.
    - No replacement or filtering of any source collection at this stage.
  - ``snapshot_files() -> Iterator[Tuple[Path, float]]``
    - Input: sequence from ``watched_files``.
    - Output: unique file+mtime pairs.
    - Only omission allowed is skip on transient ``OSError`` from disappearing
      paths.

*Dependency direction*
  - ``sys.argv`` -> ``get_manage_py_path`` -> ``StatReloader.__init__`` ->
    ``watch_file`` -> ``extra_files`` -> ``BaseReloader.watched_files`` ->
    ``snapshot_files`` -> change detection loop.
  - No dependency path may mutate module-derived or glob-derived inputs when
    adding launch-script watch data; all added data flows only through
    ``extra_files``.

Integration seam plan
---------------------

1. Preserve source-collection invariants in startup seeding:
   - resolve and register ``manage.py`` only after preserving baseline
     ``BaseReloader`` state.
   - avoid any "clear-and-rebuild" branch in ``StatReloader.__init__``.
2. Keep watcher stream additive at composition boundary:
   - ``BaseReloader.watched_files`` must continue to concatenate module,
     explicit-file, and glob sources unchanged.
3. Keep snapshot semantics additive with explicit non-regressive skip policy:
   - ``snapshot_files`` continues to dedupe and keep existing entries unless a path
     is unavailable at stat time.

Traceability loci
-----------------

*Runtime contract loci*

  - ``django/utils/autoreload.py``
    - ``StatReloader.__init__``
    - ``BaseReloader.watch_file``
    - ``BaseReloader.watched_files``
    - ``StatReloader.snapshot_files``

*Verification loci*

  - ``tests/utils_tests/test_autoreload.py``
    - ``StatReloaderTraceabilityTests``
      - ``test_auto_004_preserves_existing_watch_entries_when_adding_manage_py``

Completion status
----------------

* `AUTO-004` architectural placement is now explicit:
  - owner-boundary ownership
  - contracts and dependency direction
  - integration seam points for implementation follow-up
* This artifact remains traceable to test verification and required runtime loci.
