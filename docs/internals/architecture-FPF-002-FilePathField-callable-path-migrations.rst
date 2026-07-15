FPF-002 Architecture Artifact: stable callable ``path`` in ``FilePathField`` migrations
====================================================================================

Traceability IDs
----------------
- Requirement ID: ``FPF-002``
- Obligation mapping (from pseudocode + test contract artifacts):
  - ``FPF-002::O1``: ``path`` callable is serialized as a reconstructable migration reference.
  - ``FPF-002::O2``: migration text remains host-portable (no absolute/local path embedding).

Requirement-to-Architecture Map
-------------------------------
- O1 owns the deconstruction boundary in ``django/db/models/fields/__init__.py``
  (``FilePathField.deconstruct()``):
  - ``self.path`` is the source value for migration emission.
  - ``kwargs['path']`` must carry the callable reference object when provided.
- O1 also maps to migration serialization consumers:
  - ``django/db/migrations/writer.py`` (``MigrationWriter.serialize`` / operation serialization path)
  - ``django/db/migrations/serializer.py`` (``FunctionTypeSerializer`` for importable callables)
  - ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py`` (traceability anchors).
- O2 maps to host-independence constraints at the same seam:
  - ``FilePathField.deconstruct()`` must not normalize via environment-dependent filesystem APIs.
  - The resulting serialization chain must stay symbolic (callable path -> module import string), not absolute paths.

Ownership and Boundaries
------------------------
- Module ownership:
  - Canonical owner for requirement: ``django/db/models/fields/__init__.py``.
  - Canonical serialization owner: ``django/db/migrations/serializer.py`` and ``django/db/migrations/writer.py``.
- Existing test ownership:
  - Model fixture and callable definition: ``tests/model_fields/models.py`` (``get_local_upload_path`` and
    ``FilePathFieldCallablePathModel``).
  - Contract traceability anchors: ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py``.

Boundary Model
--------------
- Boundary S1 (Model metadata boundary):
  - Input: ``FilePathField(path=callable)`` argument at model construction time.
  - Outbound contract: ``self.path`` retains callable metadata, no filesystem expansion/evaluation.
- Boundary S2 (Migration emission boundary):
  - Input: ``FilePathField.deconstruct()`` outputs ``(name, path, args, kwargs)``.
  - Outbound contract: ``kwargs['path']`` remains callable when provided, not pre-expanded string.
- Boundary S3 (Migration serialization boundary):
  - Input: callable object from deconstructed kwargs.
  - Outbound contract: migration text contains importable callable reference expression and import set.

Dependency Direction
--------------------
- Forward flow:
  ``tests/model_fields/models.py`` model fixtures
  -> ``django/db/models/fields/__init__.py`` field deconstruction
  -> ``django/db/migrations/writer.py`` operation serialization
  -> ``django/db/migrations/serializer.py`` callable/value serialization
  -> generated migration file text.
- Dependency prohibition:
  No host/base-path dependency should be introduced by FPF-002 changes in field deconstruction;
  keep the path representation detached from runtime filesystem layout.

Integration-Seam Skeleton
-------------------------
- S2 input: ``self.path`` from ``FilePathField`` instance.
- S2 output: ``kwargs['path']`` in deconstruct remains the original callable for import-time reconstruction.
- S3 input: deconstructed callable from S2.
- S3 output: ``FunctionTypeSerializer`` produces ``<module>.<qualname>`` and required import(s).
- Host portability check: regenerate migration text across hosts should produce unchanged callable reference expression
  for equivalent importable callables.

Readiness status
----------------
- O1 and O2 mapped to explicit owners and boundaries.
- Traceability preserved via:
  - ``docs/internals/architecture-FPF-001-FilePathField-callable-path.rst`` reference for existing requirement context,
  - ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py`` for this issue’s contract IDs.
- Concrete architecture artifact updated: ``docs/internals/architecture-FPF-002-FilePathField-callable-path-migrations.rst``.
