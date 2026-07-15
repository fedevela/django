# Architecture Artifact — MED-002

## Requirement-to-architecture map

- `MED-002` (Scenario 1): given three or more `Media` objects with a satisfiable merged dependency graph, Django must return deterministic JS ordering and never emit `MediaOrderConflictWarning`.
- `MED-002` (Scenario 2): for the same 3+ media set, pairwise incremental merges and aggregate merges must produce stable warning behavior and equivalent JS order semantics.

Test traceability anchors:
- `tests/forms_tests/tests/test_media.py` `FormsMediaMergeContractTests.requirement_map`
- Scenario 1 method: `test_med_002_scenario_1_satisfiable_three_or_more_media_merges_return_deterministic_js_without_warning`
- Scenario 2 method: `test_med_002_scenario_2_pairwise_then_aggregate_merge_shapes_preserve_warning_behavior_and_deterministic_js`

## Placement decisions

1. Graph merge ownership
   - File: `django/forms/widgets.py`
   - Owner: `Media.merge`
   - Responsibility: perform multi-list order reconciliation into a single dependency-consistent JS list.

2. Merge-deferment ownership
   - File: `django/forms/widgets.py`
   - Owner: `Media.__add__` and `Media._js`
   - Responsibility: collect ordered chunks across composition hops and defer final topo-sort to a single read point.

3. Warning surface ownership
   - File: `django/forms/widgets.py`
   - Owner: `MediaOrderConflictWarning`
   - Responsibility: signal only unsatisfiable dependency cycles after merge evaluation, not due to composition shape.

4. Invocation-shape boundary
   - File: `tests/forms_tests/tests/test_media.py`
   - Owner: `FormsMediaMergeContractTests`
   - Responsibility: define contract invariants for deterministic JS semantics under different merge shapes.

## Architecture pressures (obligations)

- `MED-002` Scenario 1 pressure: replace pairwise-order-only merge behavior for `len(lists) > 2` with deterministic, satisfiable-graph resolution and stable output.
  - Boundary: algorithmic behavior of `Media.merge`.
  - Constraint: no warning on satisfiable graphs.
  - Boundary: merge result ordering must satisfy all adjacency constraints.

- `MED-002` Scenario 2 pressure: preserve equivalence across composition shapes.
  - Boundary: chunk capture (`__add__`) versus merge evaluation point (`_js`).
  - Constraint: pairwise and aggregate merging must produce the same eventual graph for satisfiable cases.

## Structural contracts

- `IMediaMergeInput` contract
  - Input: zero-or-more ordered media lists.
  - Output: list of JS assets in deterministic sequence.
  - Invariant: every list adjacency `(a, b)` implies `a` appears before `b` when feasible.

- `IMediaMergeResult` contract
  - Output guarantee for satisfiable graph: valid topological ordering, deterministic tie-break by stable iteration order, no warning.
  - Output guarantee for unsatisfiable graph: emit `MediaOrderConflictWarning`, fallback deterministic deduplicated order.

- `IMediaCompositionChunking` contract
  - Input: two `Media` instances
  - Output: merged `_js_lists`/`_css_lists` chunk lineage without immediate reordering.
  - Invariant: composition order is preserved at chunk level; final ordering is resolved once.

## Dependency-direction notes

- `base class precedence` -> `media_property` -> `Widget.media` -> `field/widget media composition` -> `Media.__add__` -> `Media._js` -> `Media.merge`.
- `Media.merge` is the sole hard dependency resolution seam for multi-list JS ordering.
- Warnings are emitted only inside `Media.merge` after cycle detection.

## Integration seam skeletons

- `S1`: Multi-list resolution seam
  - File: `django/forms/widgets.py`
  - Method: `Media.merge(*lists)`
  - Entry: chunk collection from composition boundary.
  - Exit: ordered JS list + optional `MediaOrderConflictWarning`.

- `S2`: Composition seam
  - File: `django/forms/widgets.py`
  - Method: `Media.__add__(other)`
  - Entry: left/right `Media` parts.
  - Exit: deferred chunked `Media` object.

- `S3`: Resolution seam
  - File: `django/forms/widgets.py`
  - Property: `Media._js`
  - Entry: deferred chunked media state.
  - Exit: final concrete merged JS order.

- `S4`: Contract seam
  - File: `tests/forms_tests/tests/test_media.py`
  - Methods under `FormsMediaMergeContractTests`
  - Entry: requirement-specific input shapes.
  - Exit: deterministic assertions and warning equivalence.

## Completion status

- Required obligations mapped to repository loci and ownership boundaries.
- Deterministic multi-list merge seam and warning seam identified with single responsibility each.
- `MED-002` traceability kept in canonical requirement map and method-level contract declarations.
- Completed with one new architecture artifact and no behavior changes. 
