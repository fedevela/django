AUTO-003 - Manage path canonicalization in watcher snapshot
========================================================

Purpose
-------

This document binds requirement ``AUTO-003`` to a traceable verification locus
that captures canonical path handling for ``manage.py`` launch forms.

Requirement
-----------

* Canonicalize the watched ``manage.py`` entry so that absolute, relative,
  symlinked, and subdirectory invocations produce one canonical absolute real
  path in the initial watched snapshot.

Traceability mapping
--------------------

* Requirement ID: ``AUTO-003``
* Trace test artifact: ``tests/utils_tests/test_autoreload.py::
  StatReloaderTraceabilityTests``
* Test anchors:

  * ``test_auto_003_watch_entry_for_manage_py_absolute_launch_path_is_canonical_absolute_realpath``
  * ``test_auto_003_watch_entry_for_manage_py_relative_launch_path_is_canonical_absolute_realpath``
  * ``test_auto_003_watch_entry_for_manage_py_symlink_launch_path_is_canonical_absolute_realpath``
  * ``test_auto_003_watch_entry_for_manage_py_subdirectory_launch_path_is_canonical_absolute_realpath``

Completion status
----------------

* Placeholder spec-only coverage exists for this requirement.
* No runtime behavior changes were introduced in this phase.
