AUTO-004 - Preserve existing watched paths while adding manage.py
===============================================================

Purpose
-------

Encode a non-regressive watcher contract for ``AUTO-004``:

When `python manage.py runserver` starts with an already discovered watch set,
adding ``manage.py`` must augment that set rather than replace it.

Requirement
-----------

The watch entries produced before `manage.py` augmentation (modules, globs, and
file entries) must remain present and unchanged while `manage.py` is additionally
present in the same watch collection.

Requirement-to-architecture map
-------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Rationale
   * - ``AUTO-004``
     - Preserve existing watch-path and pattern coverage in the `snapshot` and
       `extra_files` sets while adding one canonical `manage.py` entry.
     - ``django.utils.autoreload``
     - Watcher set growth must be additive; no existing modules, globs, or files
       may be dropped when enabling `manage.py` inclusion.

Traceability loci
-----------------

*Runtime contract loci*

  - ``django/utils/autoreload.py``
    - ``StatReloader.__init__``

*Verification loci*

  - ``tests/utils_tests/test_autoreload.py``
    - ``StatReloaderTraceabilityTests``
      - ``test_auto_004_preserves_existing_watch_entries_when_adding_manage_py``

Completion marker
----------------

* The requirement has explicit owner, locus, and test mapping in this file and in
  ``tests/utils_tests/test_autoreload.py``.
