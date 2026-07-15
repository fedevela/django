AUTO-006 - manage.py watch scope augmentation is gated by launch entry
======================================================================

Purpose
-------

Place ``AUTO-006`` into a stable structural boundary so launch-entry context
controls all manage.py watch-path augmentation.

Requirement
-----------

``AUTO-006`` requires that ``StatReloader`` only applies manage.py launch-path
watch augmentation when the server is launched via ``manage.py``. When runserver
is started through another entry script, the pre-existing watch scope is preserved
and no synthetic ``manage.py`` watch entry is added.

Acceptance target
-----------------

Given ``runserver`` starts through a non-``manage.py`` entry script, then
``StatReloader`` must leave the baseline watch stream unchanged while preserving
all existing baseline collection semantics.

Requirement-to-architecture map
-------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Structural obligation class
  * - ``AUTO-006``
     - Gate manage.py watch inclusion on launch script identity and retain existing
       watch scope for non-manage entrypoints.
     - ``django.utils.autoreload.get_manage_py_path`` and
       ``django.utils.autoreload.StatReloader.__init__``
     - Architecture placement (ownership boundary + conditional seam)

Pressure decomposition
---------------------

*Ownership*
  - ``django.utils.autoreload.get_manage_py_path`` owns launch-path identity
    classification (``manage.py`` vs non-manage entry scripts).
  - ``django.utils.autoreload.StatReloader.__init__`` owns startup watch-seed
    branching and should only call ``watch_file`` when ``get_manage_py_path``
    resolves to a managed launch path.
  - ``django.utils.autoreload.BaseReloader.watched_files`` owns baseline stream
    composition and remains the stable source of pre-existing modules, globs, and
    explicit files.
  - ``tests.utils_tests.test_autoreload.StatReloaderTraceabilityTests`` owns
    requirement verification and keeps the scenario boundary.

*Boundary*
  - Launch boundary: external inputs from ``sys.argv`` feed ``get_manage_py_path``.
  - Augmentation boundary: ``StatReloader.__init__`` is the only write boundary
    for this obligation.
  - Baseline-watch boundary: ``BaseReloader.watched_files`` may emit pre-existing
    stream entries; it must not gain synthetic entries from this obligation.
  - Validation boundary: ``test_auto_006_manage_py_watch_scope_is_gated_by_launch_entry_path``
    must assert non-manage entrypoint behavior and preserve previous scope.

*Contracts*
  - ``get_manage_py_path() -> Optional[Path]``
    - Input: launch arguments from ``sys.argv``.
    - Output: resolved manage.py path only when launch script semantics match the
      manage.py contract.
    - Otherwise returns ``None`` and contributes no watch-path candidate.
  - ``StatReloader.__init__(...) -> None``
    - Input: runtime options including ``check_errors`` and optional ``signal_handler``.
    - Effect: obtains manage.py candidate once; if candidate is non-``None``, call
      ``watch_file(candidate)``.
    - If candidate is ``None``, no watch path is added at this branch.
  - ``StatReloader.watched_files() -> Iterator[Path]``
    - Contract remains: existing module, explicit-file, and glob inputs from base
      state compose baseline scope.

*Dependency direction*
  - ``sys.argv`` -> ``get_manage_py_path`` -> ``StatReloader.__init__`` ->
    optional ``watch_file`` -> ``BaseReloader.watched_files``.
  - For non-manage entrypoints, the optional branch returns ``None`` and therefore
    produces no dependency edge from launch path to watched-path injection.

Traceability loci
-----------------

- Runtime contract loci

  - ``django/utils/autoreload.py``
    - ``StatReloader.__init__``
    - ``get_manage_py_path``
    - ``BaseReloader.watched_files``
    - ``BaseReloader.watch_file``

- Verification loci

  - ``tests/utils_tests/test_autoreload.py``
    - ``StatReloaderTraceabilityTests``
    - ``test_auto_006_manage_py_watch_scope_is_gated_by_launch_entry_path``

Integration seam plan
---------------------

1. Preserve existing seeding contract in ``StatReloader.__init__``:
   - call ``get_manage_py_path()`` once.
   - gate ``watch_file(manage_py)`` behind ``manage_py is not None``.
2. Keep baseline stream untouched for non-manage entry:
   - allow ``BaseReloader.watched_files`` to continue composing baseline paths as-is.
3. Keep verification as boundary check:
   - verify non-manage startup inputs alter only process-path data, not watched-file
     cardinality or contents.

Completion note
--------------

* This is a phase-only, placeholder verification artifact. No behavioral
  assertions were introduced here.
