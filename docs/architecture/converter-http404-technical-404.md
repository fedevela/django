# Converter-originated `Http404` 404 Routing Contract

Requirement scope:
- `DJ-RES-001`
- `DJ-RES-007`

## Requirement-to-architecture map
- `DJ-RES-001`
  - Route miss conversion contract in [`django/urls/resolvers.py`](django/urls/resolvers.py:260).
- `DJ-RES-007`
  - Diagnostic reason propagation through resolver payload in [`django/urls/resolvers.py`](django/urls/resolvers.py:260) and consumption in [`django/views/debug.py`](django/views/debug.py:461).
- `DJ-RES-001`, `DJ-RES-007`
  - end-to-end miss lifecycle in [`django/urls/resolvers.py`](django/urls/resolvers.py:565) -> [`django/views/debug.py`](django/views/debug.py:461).

## Ownership and boundaries
- `django/urls/resolvers.py:RoutePattern`
  - Owns converter-to-python coercion for individual path params.
  - Boundary rule: converter exceptions are interpreted as **route-match control flow**, not request processing exceptions.
- `django/urls/resolvers.py:URLResolver`
  - Owns aggregation of child probing state (`tried`) and conversion of misses into `Resolver404` for normal routing lifecycle.
  - Boundary rule: any converter-originated `Http404` should be normalized here as a routing miss, not server-error.
- `django/views/debug.py:technical_404_response`
  - Owns diagnostics rendering for routing misses.
  - Boundary rule: rendering layer must prefer converter-originated reason metadata when provided.

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

## Integration seams to implement
- Seam S-1: Conversion miss normalization
  - Module: [`django/urls/resolvers.py`](django/urls/resolvers.py)
  - Trigger: `to_python()` raises `Http404`.
  - Required effect: miss represented as routing-miss path (`Resolver404` path), preserving `tried`/`reason`.
- Seam S-2: Technical diagnostics extraction
  - Module: [`django/views/debug.py`](django/views/debug.py)
  - Trigger: `technical_404_response()` receives `Http404` from resolver flow.
  - Required effect: `reason` from payload is rendered before fallback `str(exception)`.

## Dependency direction
- `converters` → `RoutePattern.match()` (conversion outcome)
- `RoutePattern.match()` / child `pattern.resolve()` → `URLResolver.resolve()` (miss aggregation)
- `URLResolver.resolve()` → exception payload (`Resolver404`) → global error handling → `technical_404_response()`

## Implementation-ready notes
- Preserve backward-compatible resolver miss semantics for non-converter exceptions (`ValueError` already treated as local mismatch).
- Route-miss payload should remain additive: existing `path`/`tried` behavior stays intact; `reason` is additive for diagnostics.
- No admin or generic exception handling paths should be coupled to this seam.
