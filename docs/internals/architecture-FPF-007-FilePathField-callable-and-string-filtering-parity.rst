FPF-007 Architecture Artifact: parity filtering for callable vs string FilePathField path forms
=========================================================================================

Traceability IDs
----------------
- Requirement ID: ``FPF-007``
- Canonical obligations:
  - ``FPF-007::O1``: ``FilePathField.formfield()`` must pass ``match``, ``recursive``,
    ``allow_files`` and ``allow_folders`` unchanged from model metadata, independent of whether
    ``path`` is callable or literal string.
  - ``FPF-007::O2``: ``forms.FilePathField`` must execute filter and traversal logic under identical
    semantics when the resolved path source is a callable result vs static string.
  - ``FPF-007::O3``: with ``recursive=False``, ``allow_folders=True``, ``allow_files=False``,
    only immediate-level folders are selectable and this edge-case behavior is identical across path forms.

Requirement-to-Architecture Mapping
----------------------------------
- ``FPF-007::O1`` is owned by ``FilePathField.formfield()`` in
  ``django/db/models/fields/__init__.py``.
  - Input: model field metadata, including ``self.path``, ``self.match``,
    ``self.recursive``, ``self.allow_files``, ``self.allow_folders``.
  - Decision:
    - if ``self.path`` is callable, resolve once here;
    - else use the literal string/path-like value as-is.
  - Contract:
    - resolved path is passed into ``forms.FilePathField`` kwargs.
    - the four filtering options are forwarded verbatim with no parity-affecting rewrite.
  - Failure contract:
    - existing invalid path conversion failures remain unchanged.
- ``FPF-007::O2`` and ``FPF-007::O3`` are owned by
  ``FilePathField.__init__()`` in ``django/forms/fields.py``.
  - Input: resolved ``path`` + filtering/traversal options.
  - Branch:
    - ``recursive=True`` selects `os.walk` branch.
    - ``recursive=False`` selects `os.scandir` branch.
  - Shared contract:
    - no conditional behavior based on path origin (callable vs string).
    - directory/file gates from ``allow_files`` / ``allow_folders`` and ``match`` filtering apply equally.
    - ``__pycache__`` omission remains invariant.
  - Output:
    - identical candidate set and ordering for same path contents + same options.
  - Edge contract (``O3``):
    - when ``recursive=False`` and only folders allowed, only top-level directories are appended.

Placement and Ownership
-----------------------
- Primary owner of option-source normalization: ``django/db/models/fields/__init__.py``.
- Primary owner of runtime filtering/traversal: ``django/forms/fields.py`` (`FilePathField.__init__`).
- Traceability owner for validation scenarios: ``tests/model_fields/test_filepathfield_contracts.py``
  via ``FPF_007_VERIFICATION_MAP`` and
  ``FilePathFieldContractsFPF007Tests``.

Boundary model
--------------
- Boundary S1 (Model boundary → form boundary):
  - Inbound: model-level path metadata and filter flags.
  - Transition: resolve callable path if needed, convert to path-like with existing rules.
  - Outbound: resolved ``path`` plus unchanged flags to form constructor.
- Boundary S2 (Form boundary → filesystem choice boundary):
  - Inbound: resolved path and flags.
  - Transition:
    - select traversal mode by ``recursive``.
    - apply identical inclusion gates to every candidate.
  - Outbound: populated `choices` payload with stable ordering and selection.

Dependency-direction notes
-------------------------
- Structural forward dependency:
  ``tests/model_fields/test_filepathfield_contracts.py`` →
  ``django/db/models/fields/__init__.py`` (``formfield``) →
  ``django/forms/fields.py`` (`forms.FilePathField`) →
  ``os.walk`` / ``os.scandir``.
- No new external module dependencies are introduced.
- Failure direction (invalid path contract):
  path conversion/type failure in S1/S2 → deterministic exception before choice materialization.

Integration-seam skeletons
--------------------------
- S1 seam (`formfield` handoff):
  - Input contract:
    - ``path`` (callable or string/path-like), ``match``, ``recursive``, ``allow_files``, ``allow_folders``.
  - Rule:
    - resolve path for callables.
    - forward all filter flags unchanged.
  - Output:
    - kwargs forwarded to ``forms.FilePathField``.
- S2 seam (`enumeration core`):
  - Input contract:
    - concrete local directory path and filter flags.
  - Rule:
    - select `walk` vs `scandir` by ``recursive`` only.
    - emit candidates only when they pass type gate + match gate + pycache exclusion.
  - Output:
    - deterministic choices order and selection for same input set.
- S3 seam (`edge-case guard`):
  - Input contract:
    - ``recursive=False``, ``allow_folders=True``, ``allow_files=False``.
  - Rule:
    - permit only top-level directory entries; files must never pass.
  - Output:
    - folder-only immediate-depth choices.

Readiness status
----------------
- All `FPF-007` obligations are placed to explicit owners, boundaries, and seams.
- Requirement-to-test traceability is preserved through existing placeholders in
  ``tests/model_fields/test_filepathfield_contracts.py``.
- Concrete architecture artifact created:
  ``docs/internals/architecture-FPF-007-FilePathField-callable-and-string-filtering-parity.rst``.

