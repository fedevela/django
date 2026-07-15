# Converter-originated `Http404` 404 Routing Contract

Requirement scope:
- `DJ-RES-001`
- `DJ-RES-007`
- `DJ-RES-003`

## Requirement-to-architecture map
- `DJ-RES-001`
  - Route miss conversion contract in [`django/urls/resolvers.py`](django/urls/resolvers.py:260).
- `DJ-RES-002`
  - Candidate-miss continuation contract in [`django/urls/resolvers.py`](django/urls/resolvers.py:570) and converter-level normalization in [`django/urls/resolvers.py`](django/urls/resolvers.py:286).
- `DJ-RES-004`
  - Converter `ValueError` miss contract in [`django/urls/resolvers.py`](django/urls/resolvers.py:290), preserving recoverable route-miss semantics.
- `DJ-RES-005`
  - Non-`Http404`/non-`ValueError` converter failure contract in [`django/urls/resolvers.py`](django/urls/resolvers.py:304) and upward exception propagation from [`django/urls/resolvers.py`](django/urls/resolvers.py:592).
- `DJ-RES-006`
  - Success-path preservation contract in [`django/urls/resolvers.py`](django/urls/resolvers.py:595), ensuring first successful candidate is returned immediately.
- `DJ-RES-007`
  - Diagnostic reason propagation through resolver payload in [`django/urls/resolvers.py`](django/urls/resolvers.py:260) and consumption in [`django/views/debug.py`](django/views/debug.py:461).
- `DJ-RES-003`
  - Non-debug production-safe 404 handoff for converter-originated `Http404` in [`django/core/handlers/exception.py`](django/core/handlers/exception.py:34) and stable fallback in [`django/core/handlers/exception.py`](django/core/handlers/exception.py:120).
- `DJ-RES-001`, `DJ-RES-007`
  - end-to-end miss lifecycle in [`django/urls/resolvers.py`](django/urls/resolvers.py:565) -> [`django/views/debug.py`](django/views/debug.py:461).

## Ownership and boundaries
- `django/urls/resolvers.py:RoutePattern`
  - Owns converter-to-python coercion for individual path params.
  - Boundary rule: converter exceptions are interpreted as **route-match control flow**, not request processing exceptions.
- `django/urls/resolvers.py:URLResolver`
  - Owns aggregation of child probing state (`tried`) and conversion of misses into `Resolver404` for normal routing lifecycle.
  - Boundary rule: any converter-originated `Http404` should be normalized here as a routing miss, not server-error.
- `django/urls/resolvers.py:URLResolver.resolve()`
  - Owns arbitration across candidate patterns within one resolver level.
  - Boundary rule: a single candidate miss (`Resolver404`) is local; later candidates may still run.
- `django/urls/resolvers.py:URLResolver.resolve()`
  - Owns immediate dispatch when a candidate succeeds; successful match short-circuits candidate iteration.
- `django/urls/resolvers.py:RoutePattern.match()`
  - Owns converter exception classification and local translation into match state.
  - Boundary rule: `ValueError` and `Http404` are control-flow signals for match handling; other exceptions are not converted to match-miss signals.
- `django/views/debug.py:technical_404_response`
  - Owns diagnostics rendering for routing misses.
  - Boundary rule: rendering layer must prefer converter-originated reason metadata when provided.
- `django/core/handlers/exception.py:response_for_exception`
  - Owns the `Http404` branch and split between debug and non-debug handling paths.
  - Boundary rule: route-miss `Http404` must not emit technical diagnostics when `DEBUG=False`.
- `django/core/handlers/exception.py:get_exception_response`
  - Owns standard status-handler dispatch and handler failure fallback behavior.
  - Boundary rule: 404 is delivered via configured handler path, with fallback to uncaught exception handling only if handler wiring/execution fails.

## Structural contract (seam)
- Resolver miss payload (technical contract):
  - Type: `dict`
  - Keys:
    - `path` (required): remaining path at failure point.
    - `tried` (required): probe path for technical-404 debug display.
    - `reason` (optional): converter-originated `Http404` message.
- Direction:
  - `RoutePattern` / `URLResolver` create or extend payload.
- `technical_404_response` reads payload and uses `reason` as first source of user-facing diagnostic.
- Candidate-loop arbitration contract:
  - Input: ordered candidates in `self.url_patterns`.
  - For each candidate:
    - `Resolver404` ⇒ append candidate state in `tried` and continue.
    - `sub_match` ⇒ merge `kwargs` and return `ResolverMatch` without evaluating remaining candidates.
    - All misses ⇒ final `Resolver404` with aggregate `tried` (and optional `reason`).
- Non-debug 404 production-safe handoff contract:
  - Input: `response_for_exception(request, exc)` where `isinstance(exc, Http404)` and `settings.DEBUG` is false.
  - Boundary behavior: call `get_exception_response(request, get_resolver(get_urlconf()), 404, exc)`, never `technical_404_response`.
  - Output: `HttpResponse` with status code `404`, rendered from configured 404 handler (plain production output).
  - Security boundary: no interactive traceback or technical internals are included in this branch.

## Integration seams to implement
- Seam S-1: Conversion miss normalization
  - Module: [`django/urls/resolvers.py`](django/urls/resolvers.py)
  - Trigger: `to_python()` raises `Http404`.
  - Required effect: miss represented as routing-miss path (`Resolver404` path), preserving `tried`/`reason`.
- Seam S-1a: Candidate-miss continuation
  - Module: [`django/urls/resolvers.py`](django/urls/resolvers.py)
  - Trigger: one candidate raises `Resolver404` inside the parent iteration.
  - Required effect: record tried path for that candidate and continue to next candidate.
- Seam S-1b: Success dispatch fast-path
  - Module: [`django/urls/resolvers.py`](django/urls/resolvers.py)
  - Trigger: `pattern.resolve(new_path)` returns truthy `sub_match`.
  - Required effect: immediate `ResolverMatch` construction and return.
- Seam S-2: Technical diagnostics extraction
  - Module: [`django/views/debug.py`](django/views/debug.py)
  - Trigger: `technical_404_response()` receives `Http404` from resolver flow.
  - Required effect: `reason` from payload is rendered before fallback `str(exception)`.
- Seam S-3: Non-debug HTTP 404 dispatch
  - Module: [`django/core/handlers/exception.py`](django/core/handlers/exception.py)
  - Trigger: `response_for_exception` receives `Http404` while `DEBUG=False`.
  - Required effect: route via normal handler path with `status_code=404`, preserving only production-safe 404 body.
- Seam S-4: Handler fallback safety
  - Module: [`django/core/handlers/exception.py`](django/core/handlers/exception.py)
  - Trigger: `get_exception_response` cannot resolve/execute 404 handler.
  - Required effect: delegate to `handle_uncaught_exception` as a controlled failure boundary.
- Seam S-5: Exception taxonomy boundary for converter coercion
  - Module: [`django/urls/resolvers.py`](django/urls/resolvers.py)
  - Trigger: `converter.to_python(value)` invocation in `RoutePattern.match()`.
  - Required effect:
    - `ValueError` and `Http404` are converted to route-miss transitions only.
    - Any other exception types are preserved and allowed to bubble toward handler pipeline for internal-failure routing.
- Seam S-6: Non-`Resolver404` failure handling policy
  - Module: [`django/urls/resolvers.py`](django/urls/resolvers.py)
  - Trigger: candidate evaluation raises an exception not caught as `Resolver404`.
  - Required effect: no remap to routing miss; upstream middleware/exception flow determines the 500 path.

## Dependency direction
- `converters` → `RoutePattern.match()` (conversion outcome)
- `RoutePattern.match()` / child `pattern.resolve()` → `URLResolver.resolve()` (miss aggregation)
- `URLResolver.resolve()` → exception payload (`Resolver404`) → global error handling → `technical_404_response()`
- `RoutePattern.match()` (Http404) → `response_for_exception()` (`Http404`) → `get_exception_response(..., 404, exc)` → configured 404 handler / `handle_uncaught_exception` fallback
- `URLResolver.resolve()` → loop state machine (`tried`) → later `pattern` candidates (recoverable `Resolver404`)
- `URLResolver.resolve()` → immediate return path (`ResolverMatch`) when `sub_match` is present

## Implementation-ready notes
- Preserve backward-compatible resolver miss semantics for non-converter exceptions (`ValueError` already treated as local mismatch).
- Route-miss payload should remain additive: existing `path`/`tried` behavior stays intact; `reason` is additive for diagnostics.
- No admin or generic exception handling paths should be coupled to this seam.
- `DJ-RES-003` requires explicit ownership of the non-debug 404 rendering boundary so converter-originated misses stay production-safe while preserving status 404.
- For DJ-RES-002/006, candidate-loop ownership remains in `URLResolver.resolve()`; misses stay recoverable, first success remains terminal.
- For Issue #103 (`DJ-RES-004`, `DJ-RES-005`), the seam policy must remain narrow:
  - only `Http404` remains a miss remap in resolver control-flow.
  - `ValueError` stays candidate-miss control-flow, not internal-failure.
  - all other errors skip resolver remap and preserve internal error-path behavior.
