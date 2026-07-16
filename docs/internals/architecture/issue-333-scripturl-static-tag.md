# Issue 333: default static tag output architecture

## Architectural decision

The default `{% static %}` tag keeps one URL-production path for its direct and
assignment forms. `StaticNode.url(context)` owns resolution of the template
path and delegates construction of the complete asset URL to
`StaticNode.handle_simple(path)`. `StaticNode.render(context)` calls that path
once, applies the existing conditional-escaping policy once, and then either
returns the result or stores that same result in the requested context variable.

Request-prefix adaptation remains below this rendering boundary. The private
`_url_with_script_prefix(url)` adapter in `django.templatetags.static` reads the
active prefix and adapts the complete static URL. Rendering must not read the
request, reconstruct the configured static base, or apply a second prefix.

## Requirement-to-architecture map

| Requirement | Architecture pressure | Architectural home |
| --- | --- | --- |
| `SCRIPTURL-003` | Direct rendering must receive the request-prefixed URL while preserving output for an absent, empty, or root prefix. | `StaticNode.handle_simple()` produces the complete URL and passes it through `_url_with_script_prefix()`; `StaticNode.url()` is the sole URL-producing seam called by `render()`. |
| `SCRIPTURL-004` | Assignment and direct rendering must not have separate URL construction or transformation paths. | `StaticNode.render()` computes and conditionally escapes one local `url` value before branching on `varname`; it either returns or assigns that value unchanged. |

## Placement and ownership

### `django/templatetags/static.py`

`StaticNode.handle_simple(path)` remains the construction boundary. It owns the
choice between the installed-staticfiles storage adapter and fallback joining
against `STATIC_URL`. Both branches converge before returning a complete URL
adapted to the active script prefix. This is the architectural home of the
prefix-once obligation in `SCRIPTURL-003`.

`StaticNode.url(context)` remains the template-expression boundary. It resolves
`self.path` from the current context, then invokes `handle_simple()` exactly
once. It does not decide whether the tag is in direct or assignment form.

`StaticNode.render(context)` remains the presentation and assignment boundary.
Its contract for `SCRIPTURL-003` and `SCRIPTURL-004` is:

- obtain one complete asset URL through `self.url(context)`;
- preserve the existing conditional-escaping behavior;
- when `varname` is absent, return that post-escape value;
- when `varname` is present, store that same post-escape value and return an
  empty rendering; and
- propagate existing resolution, URL-generation, and escaping failures before
  assigning any partial value.

No new node type, public helper, template syntax, or request object dependency
is required. In particular, assignment is not a URL-generation adapter; it is
only the terminal destination selected after common generation and escaping.

### `tests/template_tests/syntax_tests/test_static.py`

`ScriptNameStaticMediaContractTests` is the verification boundary. The four
tests traced to `SCRIPTURL-003` and `SCRIPTURL-004` use rendered template syntax
to provide behavioral assertions covering:

1. direct rendering under a non-empty script prefix, including exactly-once
   placement before the configured static path;
2. unchanged direct output for absent, empty, and root-equivalent prefixes;
3. equality between the direct result and the value exposed by assignment for
   the same asset, settings, context, and active prefix; and
4. unchanged assignment output for absent, empty, and root-equivalent prefixes.

Tests should enter through rendered template syntax rather than calling only
the lower-level URL helper, because the requirement includes the render-versus-
assignment branch. Existing lower-level coverage remains responsible for the
storage-backed and fallback URL-construction variants.

## Dependency direction and integration seams

```text
template token -> StaticNode(path, optional varname)
                         |
                         v
                  url(context) -> handle_simple(path)
                                           |
                                           v
staticfiles storage or STATIC_URL join -> script-prefix adapter
                         |
                         v
               one complete URL -> conditional escape
                                      /          \
                              direct return   context assignment
```

The dependency direction is one-way: the template render node depends on URL
construction, which may depend on staticfiles storage and request-local prefix
state. Storage, settings, and `django.urls` do not depend on template rendering.
The direct and assignment terminals are downstream consumers of the same value;
neither may call storage or prefix adaptation independently.

## Preserved boundaries

This architecture does not alter context lookup beyond resolving the asset
expression and writing the explicitly named assignment variable. It does not
change storage output, discovery, collection, serving, or the public `static()`
helper contract. Separate `django.contrib.staticfiles` transformations remain
outside the equality boundary: `SCRIPTURL-004` compares the two forms of this
default template tag under identical inputs.

## Implementation readiness

Both requirements have an existing owner and integration seam. Implementation
is confined to enforcing the contracts at `StaticNode.url()` and
`StaticNode.render()` if needed, then converting the four traced placeholders
to behavioral tests. No topology expansion or public API is necessary.
