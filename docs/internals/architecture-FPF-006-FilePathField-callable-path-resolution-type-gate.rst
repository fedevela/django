FPF-006 Architecture Artifact: fail-fast callable path return type validation at path-resolution
================================================================================================

Traceability IDs
----------------
- Requirement ID: ``FPF-006``
- Canonical obligations:
  - ``FPF-006::O1``: if `path` is callable at formfield handoff, validate resolved value type before
    any filesystem enumeration.
  - ``FPF-006::O2``: malformed callable return values must deterministically fail with stable error
    type/message on every re-evaluation.

Requirement-to-Architecture Mapping
----------------------------------
- ``FPF-006::O1`` is owned by ``FilePathField.formfield()`` in
  ``django/db/models/fields/__init__.py``.
  - Owner (`resolution seam`): this is the point where model metadata (`self.path`) is translated into
    form kwargs.
  - Inputs:
    - ``self.path`` value from model field metadata.
    - runtime result of ``self.path()`` when callable.
  - Output contract:
    - valid string/path-like -> passes as ``path`` kwarg to ``forms.FilePathField``.
    - invalid type -> raise deterministic ``TypeError``/``ValueError`` before form field construction.
- ``FPF-006::O2`` is owned by ``FilePathField.__init__`` in ``django/forms/fields.py``.
  - Owner (`enumeration gate`): this boundary performs traversal into filesystem.
  - Inputs:
    - resolved ``path`` value provided by model boundary.
    - traversal mode (`recursive`) and type filters (`allow_files`, `allow_folders`).
  - Output contract:
    - valid path-like input proceeds to `os.walk` / `os.scandir`.
    - invalid path-like contract -> terminate with the same deterministic failure class/message and no
      partially emitted choices.

Traceability anchors (contract tests)
------------------------------------
- ``tests/forms_tests/field_tests/test_filepathfield.py`` via
  ``FPF_006_VERIFICATION_MAP``:
  - ``test_fpf_006_invalid_callable_path_return_type_raises_deterministic_path_resolution_error``
  - ``test_fpf_006_repeated_callable_path_resolution_failures_stable_for_identical_invalid_types``

Placement and Ownership
-----------------------
- Primary owner of runtime path-resolution semantics: ``django/db/models/fields/__init__.py``
  (model-formfield bridge).
- Primary owner of enumeration and fail-stop behavior: ``django/forms/fields.py``
  (`FilePathField` initialization and choice materialization).
- Contract ownership:
  - ``tests/forms_tests/field_tests/test_filepathfield.py`` owns the deterministic failure contracts
    for this issue.

Boundary model
--------------
- Boundary S1 (Model metadata -> form boundary)
  - Inbound contract:
    - `self.path` may be literal path or callable.
    - if callable, invoke in current host-runtime at model/form boundary.
  - Outbound contract:
    - pass-through for valid values only.
    - malformed return values fail before the form class sees filesystem responsibilities.
- Boundary S2 (Form boundary -> filesystem enumeration)
  - Inbound contract:
    - ``path`` must be `str` or `os.PathLike`.
  - Outbound contract:
    - no filesystem enumeration on invalid contract.
    - successful validation flows into deterministic choice enumeration.

Dependency-direction notes
--------------------------
- Stable edge direction:
  - ``tests/forms_tests/field_tests/test_filepathfield.py`` →
  - ``django/db/models/fields/__init__.py`` (`FilePathField.formfield`) →
  - ``django/forms/fields.py`` (`FilePathField.__init__`) →
  - filesystem enumeration APIs (`os.walk`, `os.scandir`).
- Failure direction (invalid path return):
  - malformed callable result → deterministic validation failure in seam S1/S2 →
  - constructor abort for that `FilePathField` instance only, no partial choices.

Integration-seam skeletons
--------------------------
- S1 seam: model ``formfield`` normalization
  - Input: ``self.path``.
  - Rule:
    1. detect callable, resolve once at this boundary;
    2. pass result only through a path contract check.
  - Output:
    - ``path`` kwargs for form field on success.
    - deterministic runtime error on non-string/path-like return.
- S2 seam: form ``FilePathField`` enumeration gate
  - Input: resolved ``path`` value and `recursive`/`match` flags.
  - Rule:
    1. validate `path` contract before selecting traversal branch.
    2. if invalid, abort before `os.walk`/`os.scandir`.
  - Output:
    - populated `self.choices` only when contract holds.
    - stable failure semantics for repeated invalid invocations.

Readiness status
---------------
- All obligations for ``FPF-006`` are mapped to explicit ownership boundaries and contracts.
- Requirement traceability preserved through existing contract placeholders and this architecture artifact.
- Concrete architecture artifact created:
  ``docs/internals/architecture-FPF-006-FilePathField-callable-path-resolution-type-gate.rst``.
