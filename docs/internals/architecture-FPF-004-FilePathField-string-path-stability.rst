FPF-004 Architecture Artifact: string-path migration and runtime parity for FilePathField
=====================================================================================

Traceability IDs
----------------
- Requirement ID: ``FPF-004``
- Canonical obligations:
  - ``FPF-004::O1``: Non-callable string ``path`` in ``FilePathField`` deconstruction remains
    migration-string-shaped.
  - ``FPF-004::O2``: migration output for existing string-path models remains compatible with
    pre-existing migration content.
  - ``FPF-004::O3``: runtime enumeration behavior for string paths remains unchanged and parity with
    callable-based models is preserved as defined by existing contract language.

Requirement-to-Architecture Mapping
----------------------------------
- ``FPF-004::O1`` and ``FPF-004::O2`` are owned by
  ``FilePathField.deconstruct()`` in ``django/db/models/fields/__init__.py``.
  - Input: field metadata where ``self.path`` may be string.
  - Output contract: ``kwargs['path']`` keeps non-empty string values as-is, callable values remain callable
    as their dedicated migration path.
  - Failure handling: no path normalization, no filesystem/stat calls, no environment-dependent string
    rewriting.
  - Traceability anchors:
    - ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py``
      ``FPF_004_VERIFICATION_MAP``
- ``FPF-004::O1`` and ``FPF-004::O3`` are owned by
  ``FilePathField.formfield()`` in ``django/db/models/fields/__init__.py``.
  - Input: ``self.path`` metadata at form-binding time.
  - Branch: ``callable(self.path)`` triggers evaluation in runtime boundary; literal strings pass-through.
  - Output contract: resulting path is forwarded unchanged for ``path=...`` to form constructor.
- ``FPF-004::O3`` is owned by ``forms.FilePathField.__init__()`` in
  ``django/forms/fields.py``.
  - Input: concrete string path plus existing match/recursive/allow flags.
  - Output contract: preserve existing enumeration logic and choice payload order.

Placement and ownership
-----------------------
- Core metadata and migration-shape ownership remains in
  ``django/db/models/fields/__init__.py``.
- Form-level path enumeration ownership remains in ``django/forms/fields.py``.
- Contract placeholders remain the only behavior anchors in:
  - ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py``
  - ``tests/model_fields/test_filepathfield_contracts.py``

Boundary model
--------------
- Boundary S1 (model metadata -> migration seam):
  - Inbound: ``FilePathField.__init__`` already stores ``self.path`` unmodified.
  - Outbound: ``deconstruct`` emits original string path only when non-default and non-callable.
- Boundary S2 (model field -> form seam):
  - Inbound: stored metadata ``self.path``.
  - Outbound: if callable -> resolved here, else passthrough literal.
  - Invariant: non-callable paths do not gain invocation or rewriting side effects.
- Boundary S3 (form constructor -> filesystem choice seam):
  - Inbound: concrete local path plus existing filter flags.
  - Outbound: ``self.choices`` + ``self.widget.choices`` follow pre-existing traversal semantics.

Dependency-direction notes
-------------------------
- Forward runtime seam:
  ``tests/* contract placeholders`` -> ``django/db/models/fields/__init__.py`` ->
  ``django/forms/fields.py``.
- Migration shape seam:
  ``django/db/models/fields/__init__.py`` -> ``django/db/migrations/writer.py`` ->
  ``django/db/migrations/serializer.py``.
- Dependency constraint for FPF-004:
  no new dependencies; keep behavior inside existing module boundaries.

Integration-seam skeletons
--------------------------
- S1 seam contract:
  - ``deconstruct() -> (name, path, args, kwargs)``
  - For string paths: ``kwargs['path']`` SHALL be literal input value (except default '' path).
- S2 seam contract:
  - ``formfield() -> kwargs['path']``
  - If callable path: evaluate in-place before handoff.
  - Else: pass literal unchanged.
- S3 seam contract:
  - ``forms.FilePathField.__init__(path, match, recursive, allow_files, allow_folders)``
  - Must keep existing directory walk + filtering behavior for non-recursive and recursive modes.

Readiness status
----------------
- Structural goal satisfied: every FPF-004 obligation has explicit owner, boundary, and seam definition.
- Requirement-to-traceability is preserved via existing contract maps in:
  ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py`` and
  ``tests/model_fields/test_filepathfield_contracts.py``.
- Concrete architecture artifact created:
  ``docs/internals/architecture-FPF-004-FilePathField-string-path-stability.rst``.
