AUTO-002 — Restart when ``manage.py`` changes on next check cycle
===============================================================

Purpose
-------

Place the deterministic requirement for ``AUTO-002`` into durable architecture
structure:

``Given a running ``python manage.py runserver`` with ``StatReloader`` and ``manage.py``
already watched, when ``manage.py`` is modified and saved, the change must be
detected in the next polling cycle and flow into the restart/reload path without
manual intervention.``

Requirement-to-architecture map
-------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Rationale
   * - ``AUTO-002``
     - Detect persisted ``manage.py`` mtime drift on the next cycle and route to
       the restart contract.
     - ``django.utils.autoreload.StatReloader.tick`` →
       ``django.utils.autoreload.BaseReloader.notify_file_changed`` →
       ``django.utils.autoreload.trigger_reload``
     - Keeps restart intent inside the reloader boundary and uses the existing
       re-exec contract instead of adding a new backend.

Pressure decomposition
---------------------

*Ownership*
  - ``StatReloader`` owns the polling and baseline state (`mtimes`) for check-cycle
    diffing.
  - ``BaseReloader`` owns change-notification policy and signal fallback handoff.
  - ``trigger_reload`` owns the process-restart contract consumed by ``restart_with_reloader``.

*Boundary*
  - ``StatReloader.tick`` is an internal polling boundary: it only consumes
    ``snapshot_files`` and emits ``notify_file_changed`` on detected drift.
  - ``BaseReloader.notify_file_changed`` is the integration seam to outside
    observers via ``file_changed`` signal.
  - ``trigger_reload`` is the hard boundary into process lifecycle orchestration
    (outside the change-detection loop).

*Contracts*
  - ``StatReloader.tick`` contract:
    - input: iterable of `(path, mtime)` from ``snapshot_files``
    - state: persists `mtimes` map across cycles
    - transition: `mtime > previous_mtime` => call ``notify_file_changed(path)``
    - output: no direct return; one control turn per polling interval.
  - ``BaseReloader.notify_file_changed`` contract:
    - input: concrete changed `path`
    - transition:
      - fire ``file_changed`` signal
      - if no receiver returns truthy value => ``trigger_reload(path)``
    - output: reload attempt or no-op on delegated handlers.
  - ``trigger_reload`` contract:
    - input: changed `filename`
    - output: `sys.exit(3)` to request supervised restart.

*Dependency direction*
  - CLI context (`sys.argv`) + module import surface -> ``BaseReloader.watched_files`` -> ``snapshot_files`` -> ``tick``.
  - ``tick`` -> ``notify_file_changed`` -> optional signal listeners.
  - signal fallthrough -> ``trigger_reload`` -> restart orchestrator loop (`restart_with_reloader`).
  - No changes in this direction from watcher backends, command runner, or external APIs.

Integration seam plan
---------------------

1. Treat ``StatReloader.tick`` baseline map as the only mutable detection state boundary
   for the requirement.
2. Keep restart delegation in ``BaseReloader.notify_file_changed`` and do not duplicate
   restart behavior in per-reloader subclasses.
3. Expose verification in ``tests/utils_tests/test_autoreload.py`` through the existing
   traceability anchor test so the obligation remains connected to runtime contract
   locations.

Concrete architecture artifact mapping
-------------------------------------

* New architecture artifact:
  - ``docs/architecture/AUTO-002-manage-py-next-check-restart-architecture.rst`` (this file)

* Runtime contract loci:
  - ``django/utils/autoreload.py``
    - ``StatReloader.tick``
    - ``BaseReloader.notify_file_changed``
    - ``trigger_reload``

* Traceability locus:
  - ``tests/utils_tests/test_autoreload.py``
    ``StatReloaderTraceabilityTests.test_auto_002_next_check_cycle_detects_manage_py_modification_and_restarts``

Completion notes
---------------

* ``AUTO-002`` has explicit ownership, seam, and dependency placement in a stable
  module boundary.
* The restart path remains owned by existing reloader contracts (`notify_file_changed` + `trigger_reload`).
* Structural readiness is high: one new architecture artifact and one traceability
  update complete the placement loop for implementation.

