# Issue #36 Architecture Artifact: DurationField invalid format messaging

## Requirement-to-architecture map

- `DUR-001`: Canonical `DurationField` default invalid pattern string contract and legacy-pattern removal target.
- `DUR-002`: Keep model and form validation failure timing unchanged while ensuring corrected default is used on the default branch.
- `DUR-005`: Preserve explicit caller-provided `error_messages["invalid"]` precedence over defaults in both validation paths.

## Placement decisions and ownership boundaries

- **Model locus**: `django.db.models.fields.DurationField` in `django/db/models/fields/__init__.py`
  - Owns model-side `DurationField.default_error_messages["invalid"]`.
  - Owns model validation entrypoint behavior in `DurationField.to_python`.
  - Boundary: `models.Field` base behavior and constructor-based `error_messages` merge.
- **Form locus**: `django.forms.fields.DurationField` in `django/forms/fields.py`
  - Owns form-side `DurationField.default_error_messages["invalid"]` and `DurationField.to_python`.
  - Boundary: `forms.Field` base behavior and form `clean` orchestration.
- **Shared parsing seam**: `django.utils.duration.parse_duration`
  - Shared dependency for both model and form parsing of raw values.
  - Boundary: utility parser should remain unchanged by this issue; only consumers’ error mapping changes.
- **Cross-layer seam**: message contract flow from field class `default_error_messages` into `ValidationError(code="invalid")`.
  - This seam is the authoritative integration boundary for `DUR-005`.

## Interface / contract artifacts

- **Message contract**:
  - `invalid` branch must source text from `self.error_messages["invalid"]` in both model and form classes.
  - The default for this key is the corrected pattern `"[DD] [[HH:]MM:]ss[.uuuuuu]"`.
- **Validation contract**:
  - Default branch emits `invalid` only after parse failure (`ValueError`/`None` handling model path, `None` handling form path), with no timing change to current branches.
  - `overflow` handling in form path remains separate and unchanged.
- **Override contract**:
  - If caller passes custom `error_messages={"invalid": ...}`, that value is already selected by constructor merge and must pass through unchanged; no path should special-case default text in that case.

## Dependency direction

- `Django form/model DurationField -> base field classes -> shared utility parser`.
- Data flow: `input value -> to_python -> parse_duration -> ValidationError(code="invalid"/"overflow") -> message text from merged error_messages`.
- Directional ownership:
  - message string definitions remain local to each class.
  - parse logic remains in shared utility.
  - branch decisions remain local to each field implementation.

## Integration-seam skeleton for implementation

- **Model implementation seam**
  - Update `DurationField.default_error_messages["invalid"]` string in `django/db/models/fields/__init__.py` only.
  - Ensure `to_python` uses merged `self.error_messages['invalid']` for malformed values (already structurally in place).
- **Form implementation seam**
  - Ensure form-side `to_python` retains current exception branches and final malformed branch uses `self.error_messages['invalid']` (already structurally in place).
  - Keep `default_error_messages["invalid"]` aligned with the canonical pattern.

## Traceability references (logical acceptance coverage)

- `tests/model_fields/test_durationfield.py` carries `DUR-001`, `DUR-002`, `DUR-005` test identifiers for model and form-path behavior.
- `tests/forms_tests/field_tests/test_durationfield.py` carries `DUR-001`, `DUR-002`, `DUR-005` test identifiers for form-path behavior.
- Existing pseudocode comments in:
  - `django/db/models/fields/__init__.py` around `DurationField`
  - `django/forms/fields.py` around `DurationField`

## Completion status

- Requirement-to-architecture trace is complete for all three obligations.
- Concrete architecture artifact created: this file.
- Structural readiness: clear ownership, message contract, override boundary, dependency direction, and integration seams are defined.
