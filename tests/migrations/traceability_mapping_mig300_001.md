# MIG-300-001 requirement-to-verification map

- MIG-300-001: Serialize plain enum defaults using member-name syntax
- Requirement coverage: `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_001_plain_enum_member_default_renders_as_member_name_index`
- Requirement coverage: `tests/migrations/test_writer_enum_default_contracts.py::MigrationWriterEnumDefaultContractTests.test_mig_300_001_non_enum_default_stays_in_existing_serialization_form`

## MIG-300-001 architecture (Yesod/SPARC-A)

- Requirement to architecture pressure map:
  - `MIG-300-001` → `django/db/migrations/serializer.py:EnumSerializer.serialize`
    - Pressure: deterministic literal shape for plain `enum.Enum` members (`Status['GOOD']`).
    - Pressure: keep existing non-enum and choices-style enum behavior untouched.
    - Pressure: preserve serializer contract stability (`(code_string, import_set)`).
  - `MIG-300-001` → `tests/migrations/test_writer_enum_default_contracts.py`
    - Pressure: boundary verification coverage for both plain enum and non-enum default serialization paths.

- Ownership and module placement:
  - Owning module for literal formatting logic: `django.db.migrations.serializer.EnumSerializer`.
  - Owning module for dispatch of values to serializer classes: `django.db.migrations.serializer.serializer_factory`.
  - Boundary that must remain stable: writer contracts consume only rendered text + imports; no consumer assumes internal enum-branch implementation details.

- Structural contracts and interfaces:
  - Contract at `EnumSerializer.serialize`:
    - Input: enum-like instance (runtime `enum.Enum` member).
    - Output: tuple of `(rendered_default_literal, import_set)`.
    - For plain `enum.Enum` members under `MIG-300-001`: render `"{module}.{ClassName}['{MEMBER_NAME}']"`.
    - For model-choice-like enums: defer/retain existing value-based serialization branch.
  - Contract guard:
    - No behavior changes in non-enum paths; only the enum-default emission branch is structurally permitted to change.

- Dependency direction:
  - `EnumSerializer` depends downward on `serializer_factory(self.value.value)` to keep scalar/value serialization reusable.
  - `EnumSerializer` adds module-level import dependency (`import {enum_module}`) in import set.
  - Migration writer depends on serializer output contract only; does not require enum internals.

- Integration seam(s):
  - Render seam: `EnumSerializer.serialize` is the dedicated transformation seam for enum default rendering.
  - Policy seam: choice/choices-style enums and plain enum member handling are policy branches inside this method, preventing cross-module coupling.
  - Verification seam: test contract methods in `MigrationWriterEnumDefaultContractTests` validate both branch outcomes.

- Readiness checks (architecture only):
  - Every traced obligation has a single owning implementation locus.
  - Non-enum behavior boundary is explicit and preserved by design.
  - At least one architecture artifact updated with traceability and placement.
  - Repository structure remains coherent for later implementation by keeping change localized to serializer contract owner.
