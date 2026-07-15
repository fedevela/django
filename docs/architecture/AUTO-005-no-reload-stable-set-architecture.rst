AUTO-005 - No synthetic reload when watched-set remains stable
=============================================================

Purpose
-------

Place the deterministic requirement for ``AUTO-005`` into stable structure:

``Given ``StatReloader`` is running with a stable watched set and no filesystem
mutations on ``manage.py`` or any baseline watched path, a full polling cycle
must not emit reload/restart notifications.``

Requirement
-----------

If ``manage.py`` and all other watched paths are unchanged across repeated check
cycles, no synthetic restart cycle is allowed. This forbids initial watcher
state seeding from becoming a false-positive restart event.

Requirement-to-architecture map
-------------------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Obligation
     - Architectural locus
     - Rationale
   * - ``AUTO-005``
     - Ensure first-seen file states are seeded only as baselines and only
       positive mtime drift (`mtime > old`) triggers notification.
     - ``django.utils.autoreload.StatReloader.tick`` plus startup watch seeding
       path in ``django.utils.autoreload.StatReloader.__init__``
     - Prevents initial baseline population from being interpreted as a restart
       condition.

Pressure decomposition
---------------------

*Ownership*
  - ``django.utils.autoreload.StatReloader.__init__`` owns startup watch
    population and ensure ``manage.py`` is represented before the first
    `snapshot_files` pass.
  - ``django.utils.autoreload.StatReloader.tick`` owns polling state and per-cycle
    baseline comparisons (`mtimes`).
  - ``django.utils.autoreload.BaseReloader.notify_file_changed`` owns the
    reload handoff contract once a positive change is detected.
  - ``django.utils.autoreload.BaseReloader.watched_files`` and
    ``django.utils.autoreload.StatReloader.snapshot_files`` own snapshot input and
    mtime collection boundaries.
  - ``tests.utils_tests.test_autoreload.StatReloaderTraceabilityTests`` owns
    requirement verification.

*Boundary*
  - ``StatReloader.tick`` is the temporal boundary where watch state transitions
    from "unseen/seeded" to "compared" can occur.
  - ``snapshot_files`` is the source-of-truth boundary for emitted `(path, mtime)`
    tuples and intentionally omits transiently missing files on `OSError`.
  - ``notify_file_changed`` is the outbound boundary to signal observers and
    optional process restart path.
  - `sys.argv`/`get_manage_py_path` remain launch-time input boundaries feeding
    seeding only, not comparison semantics.

*Contracts*
  - ``StatReloader.__init__() -> None``
    - Seeds baseline watch coverage by calling
      ``get_manage_py_path -> self.watch_file`` when available.
    - Does not itself emit notification; it only prepares deterministic baseline
      inputs.
  - ``StatReloader.tick() -> Iterator[None]``
    - Input: baseline map `mtimes` and stream from ``snapshot_files``.
    - For each `(filepath, mtime)`:
      - unseen path: persist ``mtimes[path] = mtime`` and continue.
      - `mtime == old_time`: keep state and continue with no notify.
      - `mtime < old_time`: treat as no change for this contract and continue.
      - `mtime > old_time`: call ``notify_file_changed(path)``.
    - If no path causes positive drift, emit no restart signal this cycle.
  - ``BaseReloader.notify_file_changed(path) -> None``
    - Input: concrete changed `path`.
    - Output: either callback-based handling or eventual fallback to restart.

*Dependency direction*
  - Launch boundary -> ``get_manage_py_path`` -> ``StatReloader.__init__`` ->
    ``BaseReloader.watch_file`` -> ``BaseReloader.watched_files`` -> ``snapshot_files`` ->
    ``StatReloader.tick`` -> ``notify_file_changed``.
  - ``tick`` has mutable state direction only in `self._mtimes`-like local map
    retained across polling cycles; no backward dependency to launch context.
  - No backward dependency from comparison policy to watcher-backend transport.

Integration seam plan
---------------------

1. Establish steady-state policy in ``StatReloader.tick``:
   - keep baseline seeding logic on first-seen paths.
   - treat ``mtime == old`` and ``mtime < old`` as non-notifying branches.
   - emit notifications only on strict positive drift.
2. Keep startup inclusion of launch-path within existing seeding boundary:
   - continue to register ``manage.py`` through ``watch_file`` in ``__init__``.
   - ensure this inclusion cannot itself route into notification before baseline
     comparison state is initialized.
3. Preserve verification anchor in
   ``test_auto_005_no_reload_when_watched_set_is_stable`` so architecture maps
   to explicit steady-state contract.

Traceability loci
-----------------

*Runtime contract loci*

  - ``django/utils/autoreload.py``
    - ``StatReloader.__init__``
    - ``BaseReloader.watched_files``
    - ``StatReloader.snapshot_files``
    - ``StatReloader.tick``
    - ``BaseReloader.notify_file_changed``

*Verification loci*

  - ``tests/utils_tests/test_autoreload.py``
    - ``StatReloaderTraceabilityTests``
      - ``test_auto_005_no_reload_when_watched_set_is_stable``

Completion status
----------------

* ``AUTO-005`` now has explicit architecture ownership, boundary, contract,
  dependency direction, and integration seam definitions.
* The obligation is structurally placed in ``django.utils.autoreload`` and
  traced through ``tests/utils_tests/test_autoreload.py``.
* This is the first concrete architecture artifact for `AUTO-005`, enabling
  deterministic implementation follow-up.

