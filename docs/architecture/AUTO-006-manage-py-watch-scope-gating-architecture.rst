AUTO-006 - manage.py watch scope augmentation is gated by launch entry
======================================================================

Purpose
-------

Bind ``AUTO-006`` to an explicit traceability artifact before any behavioral
assertions are introduced.

Requirement
-----------

``AUTO-006`` requires that ``StatReloader`` only applies manage.py launch-path
watch augmentation when the server is launched via ``manage.py``. When runserver
is started through another entry script, the pre-existing watch scope is preserved
and no synthetic ``manage.py`` watch entry is added.

Requirement-to-architecture map
-------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Test obligation locus
   * - ``AUTO-006``
     - Gate manage.py watch inclusion on launch script identity and retain existing
       watch scope for non-manage entrypoints.
     - ``django.utils.autoreload.get_manage_py_path`` plus
       ``django.utils.autoreload.StatReloader.__init__``
     - ``tests.utils_tests.test_autoreload.StatReloaderTraceabilityTests.test_auto_006_manage_py_watch_scope_is_gated_by_launch_entry_path``

Traceability loci
-----------------

- Runtime contract loci

  - ``django/utils/autoreload.py``
    - ``get_manage_py_path``
    - ``StatReloader.__init__``
    - ``StatReloader.watched_files``

- Verification loci

  - ``tests/utils_tests/test_autoreload.py``
    - ``StatReloaderTraceabilityTests``
    - ``test_auto_006_manage_py_watch_scope_is_gated_by_launch_entry_path``

Completion note
--------------

* This is a phase-only, placeholder verification artifact. No behavioral
  assertions were introduced here.
