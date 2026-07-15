# Architecture Artifact — MED-003

## Requirement-to-architecture map

- `MED-003` Scenario 1: satisfiable 3+ merge with deduplication-created intermediate boundaries must never raise a warning unless final merged constraints are unsatisfiable.
- `MED-003` Scenario 2: warnings must not be emitted from intermediate boundary artifacts that are not part of final combined constraints.
- `MED-003` Scenario 3: unsatisfiable final ordering constraints must emit `MediaOrderConflictWarning` with a pair that exists as a real contradiction in the final graph.

Traceability anchors:
- `tests/forms_tests/tests/test_media.py` `FormsMediaMergeContractTests.requirement_map`
- `tests/forms_tests/tests/test_media.py`:
  - `test_med_003_scenario_1_no_warning_for_deduplication_artifacts_when_final_graph_is_satisfiable`
  - `test_med_003_scenario_2_boundary_duplicate_warning_emission_removed_when_only_intermediate_artifact`
  - `test_med_003_scenario_3_warn_only_for_real_unsatisfiable_final_ordering_conflict`
- `django/forms/widgets.py` `Media.merge` comments and warning path structure

## Placement and ownership

1. Merge-semantics owner:
   - File: `django/forms/widgets.py`
   - Owner: `Media.merge(*lists)`
   - Responsibility: compute one final dependency graph for all input lists and perform conflict gating against that final graph.

2. Constraint-capture owner:
   - File: `django/forms/widgets.py`
   - Owner: `Media.__add__` + `Media._js` + `Media._css`
   - Responsibility: defer ordering to a single merge frontier so pairwise composition does not itself become a conflict source.

3. Warning surface owner:
   - File: `django/forms/widgets.py`
   - Owner: `MediaOrderConflictWarning` emission site in `Media.merge`
   - Responsibility: emit warning only when final merged graph has no valid topological ordering.

4. Test-contract owner:
   - File: `tests/forms_tests/tests/test_media.py`
   - Owner: `FormsMediaMergeContractTests`
   - Responsibility: keep MED-003 obligations in the contract map and scenario-level intent.

## Architecture pressures

- `Boundary pressure` (Scenario 1): collapse warning decision to final merge edge set (`merge(*lists)`) and prevent earlier composition boundaries from emitting independently.
- `Constraint pressure` (Scenario 2): maintain merge boundaries while forbidding warning eligibility from deduplication artifacts.
- `Pair pressure` (Scenario 3): require warning pair derivation from a contradiction edge in the final graph (or deterministic representative of final-cycle context).

## Structural contracts

- `IMediaConstraintGraphFinal` contract
  - Input: one ordered vector per chunk from full composition path.
  - Output: final graph with all adjacency edges accumulated once per merge call.
  - Constraint: only this graph is eligible for satisfiable/unsatisfiable classification.

- `IMediaConflictEligibility` contract
  - Input: final graph and in-degree state after deterministic topo processing.
  - Success path: all nodes scheduled, no warning.
  - Failure path: emit `MediaOrderConflictWarning` only when topo schedule cannot complete.

- `IMediaConflictPair` contract
  - Input: unsatisfiable final graph.
  - Output: reported pair `(left, right)` must be a real contradicting pair in final graph context.
  - Determinism: pair selection strategy is defined within final-graph traversal and independent of transient list partitioning.

## Dependency direction and seam map

Dependency direction:
- `media_property` -> widget/media composition -> `Media.__add__` chunk capture -> `Media._js` -> `Media.merge`.

Primary seam:
- `S-MED003-G`: final graph build in `Media.merge` (authoritative for warning eligibility).

Secondary seams:
- `S-MED003-C`: `Media.__add__` chunk collection (must remain ordering-preserving, non-gating).
- `S-MED003-W`: warning emission site (`warnings.warn` + `MediaOrderConflictWarning`) tied to final topo failure only.

## Integration-seam skeletons

- `S1` — Final graph seam
  - Location: `django/forms/widgets.py`, `Media.merge`
  - In: all non-empty list chunks
  - Out: topologically ordered list and warning/none.

- `S2` — Composition seam
  - Location: `django/forms/widgets.py`, `Media.__add__`
  - In: left/right media chunks
  - Out: deferred chunk lineage (`_js_lists`, `_css_lists`).

- `S3` — Contract seam
  - Location: `tests/forms_tests/tests/test_media.py`, `FormsMediaMergeContractTests`
  - In: named MED-003 scenario fixtures
  - Out: requirement traceability and expected warning behavior.

## Readiness check

- Each MED-003 logic obligation is assigned to a boundary or contract.
- Warning semantics are now structurally owned by the final merge seam.
- The artifact set includes a dedicated MED-003 architecture document and remains structurally focused.
