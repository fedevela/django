FPF-005 Architecture Artifact: fail-fast serialization for non-importable `path` callables
=======================================================================================

Traceability IDs
----------------
- Requirement ID: ``FPF-005``
- Canonical obligations:
  - ``FPF-005::O1``: ``path`` callables must be importable/reconstructable during migration
    serialization (explicit gate before migration file emission).
  - ``FPF-005::O2``: non-importable callable `path` must abort migration generation with no
    opaque migration fallback.

Requirement-to-Architecture Mapping
----------------------------------
- ``FPF-005::O1`` is owned by ``FilePathField.deconstruct()`` in
  ``django/db/models/fields/__init__.py`` and reinforced by ``FunctionTypeSerializer.serialize()`` in
  ``django/db/migrations/serializer.py``.
  - Owner-1 (`deconstruction boundary`): validate callable `path` shape before committing migration
    payload.
  - Owner-2 (`symbol reconstruction boundary`): canonicalize/reject callable imports in serializer
    before string output.
  - Input: ``self.path`` from model metadata.
  - Output contract:
    - callable and reconstructable -> ``kwargs['path'] = self.path`` reaches serializer chain.
    - non-importable callable -> fail-fast `ValueError` with deconstructability/import-path context.
- ``FPF-005::O2`` is owned by ``FunctionTypeSerializer.serialize()`` and
  ``ModelFieldSerializer.serialize()`` in ``django/db/migrations/serializer.py``.
  - Owner-1 (`callable path serializer`): reject lambdas, missing module metadata, and local/nested
    qualnames.
  - Owner-2 (`field serialization pipeline`): propagate the same failure; no exception swallowing or
    alt value synthesis.
  - Input: deconstructed `(path, args, kwargs)` for any `DeconstructableSerializer` field.
  - Output contract:
    - all serialized primitives/callables -> migration string + imports emitted.
    - any non-reconstructable callable -> migration write aborts before file creation.
  - Traceability anchors:
    - ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py`` via
      ``FPF_005_VERIFICATION_MAP`` entries:
      - ``test_fpf_005_makemigrations_fails_when_path_callable_is_not_importable``
      - ``test_fpf_005_no_opaque_path_value_written_for_invalid_callable``

Placement and Ownership
-----------------------
- Primary metadata owner: ``django/db/models/fields/__init__.py`` keeps the rule for when `path`
  remains object state versus validated migration payload.
- Primary serialization owner: ``django/db/migrations/serializer.py`` owns deconstructability decisions
  and migration-time fail-fast behavior.
- Contract owner: ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py`` keeps issue
  scenario language and deterministic test names.

Boundary model
--------------
- Boundary S1 (Model metadata -> migration payload)
  - Inbound: ``FilePathField.path`` captured at model init and retained on the field.
  - Outbound contract: only importable callable objects continue into deconstruct payload; invalid callables
    are rejected before migration rendering.
- Boundary S2 (Payload -> serializer)
  - Inbound: ``ModelFieldSerializer.serialize()`` receives `(path, args, kwargs)`.
  - Outbound contract: serializer never emits fallback literals for rejected callables; failure is terminal.
- Boundary S3 (Serializer -> migration text emission)
  - Inbound: imported migration expressions emitted by serializer(s).
  - Outbound contract: malformed payload prevents `MigrationWriter` from producing a migration file.

Dependency-direction notes
--------------------------
- Structural direction:
  ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py` ->
  ``django/db/models/fields/__init__.py`` ->
  ``django/db/migrations/serializer.py`` (``FunctionTypeSerializer`` / ``ModelFieldSerializer``).
- Failure direction (for invalid callables):
  serializer error -> caller propagation -> migration command abort -> no `__pycache__/000X` file emission.
- No new dependencies introduced; only deterministic, synchronous validation in existing seam
  boundaries.

Integration-seam skeletons
--------------------------
- S1 seam (`FilePathField.deconstruct`):
  - Input: ``self.path``.
  - Rule: if callable, mark as serializable candidate; if not importable, raise a deterministic serialization
    error before returning final deconstruction payload.
- S2 seam (`FunctionTypeSerializer.serialize`):
  - Input: callable candidate.
  - Rule: `lambda` / no module / local-nested `<locals>` -> raise `ValueError` with importability framing.
  - Output: ``'<module>.<qualname>'`` + imports when valid.
- S3 seam (`ModelFieldSerializer.serialize`):
  - Input: deconstructed field payload.
  - Rule: delegate to `serialize_deconstructed`; propagate any `ValueError`.
  - Output: no opaque ``path`` serialization fallback.

Readiness status
----------------
- All traced obligations for ``FPF-005`` are placed in explicit module ownership and boundary contracts.
- Existing traceability remains intact through ``FPF_005_VERIFICATION_MAP`` in
  ``tests/migrations/test_contract_fpf_002_file_path_callable_reference.py``.
- Concrete architecture artifact updated:
  ``docs/internals/architecture-FPF-005-FilePathField-callable-path-serialization-gate.rst``.
