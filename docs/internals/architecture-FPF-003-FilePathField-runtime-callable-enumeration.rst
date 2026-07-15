FPF-003 Architecture Artifact: host-runtime callable path resolution during FilePathField enumeration
===============================================================================================

Traceability IDs
----------------
- Requirement ID: ``FPF-003``
- Logical obligations:
- ``FPF-003::O1``: resolve callable ``path`` in current process context when materializing formfield.
- ``FPF-003::O2``: enumerate file/choice candidates against the runtime-resolved path in form layer so host-local directory contents are observed.

Requirement-to-Architecture Map
-------------------------------
- O1 is owned by ``FilePathField.formfield`` in ``django/db/models/fields/__init__.py``.
  - Input: ``self.path`` metadata on model field instance.
  - Contract: callable values are evaluated at this boundary to produce a concrete path for this form instance.
  - Output: resolved ``path`` is injected into ``forms.FilePathField`` construction kwargs.
- O2 is owned by ``forms.FilePathField.__init__`` in ``django/forms/fields.py``.
  - Input: resolved concrete path, ``match``, ``recursive``, ``allow_files``, ``allow_folders``.
  - Contract: form field choices are built from filesystem traversal at instance construction.
  - Output: ``self.choices`` and ``self.widget.choices`` reflect the host-visible directory contents at call time.
- Traceability anchors remain in ``tests/model_fields/test_filepathfield_contracts.py`` as placeholder contract names:
  - ``test_FPF_003_runtime_callable_invocation_uses_current_host_path_for_choice_enumeration``
  - ``test_FPF_003_host_locality_choices_observe_current_runtime_path_output``

Placement and Ownership
-----------------------
- Metadata owner: ``django/db/models/fields/__init__.py`` retains policy about when callable metadata is resolved.
- Enumeration owner: ``django/forms/fields.py`` controls concrete traversal strategy and choice ordering.
- Contract owner: ``tests/model_fields/test_filepathfield_contracts.py`` owns scenario names and expected behavior language for execution-phase tests.

Boundary Model
--------------
- Boundary S1 (Model-form conversion boundary):
  - Origin: model field state at ``FilePathField.formfield`` call site.
  - Inbound contract: ``self.path`` may be callable or string.
  - Outbound contract: if callable, evaluate exactly here and in the current runtime; never cache at import-time.
- Boundary S2 (Form-path enumeration boundary):
  - Origin: resolved path from S1 into ``forms.FilePathField``.
  - Inbound contract: enumeration uses the provided path and local environment only.
  - Outbound contract: per-instance ``choices`` correspond to observed filesystem entries for that host/session.

Dependency Direction
--------------------
- Backward direction:
  - Tests exercise model-field contract intent in ``tests/model_fields/test_filepathfield_contracts.py``.
- Forward direction:
  - ``django/db/models/fields/__init__.py`` -> ``django/forms/fields.py`` via ``formfield(..., form_class=forms.FilePathField, path=resolved_path)``.
- No additional cross-domain dependencies are required for this requirement; keep traversal local to standard-library ``os``/``scandir`` calls in ``django/forms/fields.py``.

Integration-Seam Skeleton
-------------------------
- S1 seam payload contract:
  - ``(path_value, match, recursive, allow_files, allow_folders)`` enters ``forms.FilePathField`` constructor.
  - ``path_value`` must be concrete filesystem path string from local callable evaluation or configured literal.
- S2 seam payload contract:
  - Produced by ``forms.FilePathField.__init__`` as populated ``choices``/``widget.choices``.
  - Includes blank choice only when not required (unchanged from existing field semantics).
- S3 seam behavior:
  - Callable resolution at S1 must occur before any directory walk in S2 so host-local directory layout is selected consistently within the call.

Readiness status
---------------
- O1 and O2 are mapped to explicit modules, seams, and contracts.
- One concrete architecture artifact created:
  - ``docs/internals/architecture-FPF-003-FilePathField-runtime-callable-enumeration.rst``.
- Structural focus is preserved: only boundaries, ownership, dependency direction, and integration seams are introduced.
