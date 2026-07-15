FPF-001 Architecture Artifact: callable ``path`` on ``FilePathField``
==================================================================

Traceability IDs
----------------
- Requirement ID: ``FPF-001``
- Logical obligations:
- O1: store ``path`` as callable metadata at model definition time.
- O2: avoid filesystem/materialized path resolution during model/module import.

Requirement-to-Architecture Mapping
----------------------------------
- O1 is owned by ``FilePathField.__init__`` in ``django/db/models/fields/__init__.py`` for state capture.
- O1 deconstruction traceability is owned by ``FilePathField.deconstruct`` in ``django/db/models/fields/__init__.py``.
- O2 import-time boundary control is owned by ``FilePathField.__init__`` and ``FilePathField.formfield`` in ``django/db/models/fields/__init__.py``.
- O2 validation fixture is represented in ``tests/model_fields/models.py`` and ``tests/model_fields/test_filepathfield_contracts.py``.

Placement and ownership
----------------------
- Core field metadata policy belongs in ``django/db/models/fields/__init__.py`` where ``FilePathField`` is defined.
- Model-definition usage fixture stays in ``tests/model_fields/models.py`` for deterministic import-time registration.
- Contract observation layer stays in ``tests/model_fields/test_filepathfield_contracts.py`` with placeholder scaffolds.

Boundary model
--------------
- Import-time boundary (model class construction):
- Input side: field constructor arguments, including ``path``.
- Invariant: field registration and metadata object creation must not execute callable.
- Output side: field instances expose ``field.path`` as original object.
- Form-boundary:
- Trigger side: ``formfield()`` call from model form construction.
- Role: optional deferred callable evaluation may occur at this boundary in a later implementation step.
- Constraint: only no-argument, importable callables are accepted for ``path`` in this requirement.

Contract scaffolds
------------------
- ``FilePathField.path`` stores either:
- default string/path value or
- top-level callable object with zero required positional args.
- ``FilePathField.deconstruct`` must serialize ``path`` value as-is (object identity when non-default), preserving migration/state round-trip intent.
- If callable serialization cannot be guaranteed import-safe, implementation should fail fast at the migration/form boundary, not by eager call at import time.

Dependency direction
-------------------
- Outgoing dependency from models layer: ``django/db/models/fields/__init__.py`` -> ``django/forms/fields.py`` through ``forms.FilePathField`` in ``formfield`` adapter layer.
- Incoming dependency from app settings/tests: models in ``tests/model_fields/models.py`` import ``settings`` and provide callable for field metadata only.
- No new dependencies required for O1/O2 beyond existing ones.

Integration seams
-----------------
- Seam S1: metadata seam at ``FilePathField.__init__`` and ``self.path`` assignment.
- Seam S2: migration/form seam at ``FilePathField.deconstruct`` kwargs emission.
- Seam S3: runtime evaluation seam at ``FilePathField.formfield`` where ``path`` is consumed by form field construction.

Readiness gates
---------------
- O1 mapped to model metadata ownership and deconstruction boundary.
- O2 mapped to import-time boundary and form-time deferred boundary.
- All changed files in this phase are requirement-traceable:
- ``django/db/models/fields/__init__.py``.
- ``tests/model_fields/models.py``.
- ``tests/model_fields/test_filepathfield_contracts.py``.
- New architecture artifact:
- ``docs/internals/architecture-FPF-001-FilePathField-callable-path.rst``.

