# Issue 332: request-scoped static and media URL architecture

## Architectural decision

The request-prefix adapter belongs in `django.templatetags.static` as one
private, side-effect-free function with the implementation contract
`_url_with_script_prefix(url) -> url`. It reads the active prefix from
`django.urls.get_script_prefix()` at call time and returns a URL; it does not
accept a request, cache request state, or mutate settings or storage objects.

`django.urls` continues to own request-local `SCRIPT_NAME` lifecycle. WSGI and
ASGI handlers continue to set that state. Static/media template URL generation
may read it, but storage and settings layers must not depend on request state.

## Requirement-to-architecture map

| Requirement | Architecture pressure | Architectural home |
| --- | --- | --- |
| `SCRIPTURL-001` | One request-prefix boundary must cover both installed-staticfiles and fallback static URL composition. | Adapt the complete result in `StaticNode.handle_simple()` through `_url_with_script_prefix()`. |
| `SCRIPTURL-002` | Media prefix rendering needs the same request-prefix semantics as static rendering. | Adapt the configured base in `PrefixNode.handle_simple()`; `get_media_prefix` already enters through this method. |
| `SCRIPTURL-008` | Prefix state must be isolated by request and never retained by a long-lived node or storage instance. | `_url_with_script_prefix()` reads `get_script_prefix()` for every generation and remains stateless. |
| `SCRIPTURL-009` | Empty, absent, and root-equivalent prefixes must preserve the current output byte-for-byte. | The adapter returns its input unchanged when no non-root application prefix is active. |
| `SCRIPTURL-010` | Prefixing must not replace the configured base or detach the subordinate asset path. | Static adaptation occurs after storage/fallback path composition; prefix-tag adaptation receives the full configured base. URL parsing/reassembly preserves path, query, and fragment components. |
| `SCRIPTURL-011` | External ownership boundaries must remain external. | The adapter treats a scheme or network location as an external URL and returns it unchanged. |

## Placement and contracts

### `django/templatetags/static.py`

Add the private `_url_with_script_prefix(url)` adapter beside the shared
prefix-node implementation. Its input is already IRI-safe or is the result of
a storage backend. Its output contract is:

- return absolute and protocol-relative URLs unchanged;
- return the input unchanged for an empty or root active prefix;
- return the input unchanged when its path already begins with the complete
  active prefix on a path-segment boundary;
- otherwise insert the active prefix before the application-relative path
  exactly once, preserving query and fragment data; and
- retain no state and propagate existing parsing or conversion failures.

`PrefixNode.handle_simple()` remains the owner of setting lookup and IRI
conversion. It hands its converted `STATIC_URL` or `MEDIA_URL` base to the
adapter immediately before returning it.

`StaticNode.handle_simple()` remains the owner of asset-path composition. Both
branches first finish their existing work:

1. installed staticfiles: `staticfiles_storage.url(path)` produces the complete
   candidate URL;
2. fallback: the quoted path is joined beneath the configured static base.

The selected complete candidate is then handed to the adapter. This placement
keeps custom storage output opaque, preserves external storage URLs, and avoids
putting request dependencies into `django.core.files.storage` or
`django.contrib.staticfiles.storage`.

### `django/urls/base.py`

No structural change is required. `set_script_prefix()` and
`get_script_prefix()` remain the lifecycle port for request-local prefix state.
The new adapter has a one-way dependency on the public getter.

### `tests/template_tests/syntax_tests/test_static.py`

The existing six traced placeholders are the verification seam. During
implementation they should become behavioral tests using
`override_script_prefix` to exercise relative static/media bases, sequential
request-prefix changes, empty/root prefixes, base/path preservation, and
absolute plus protocol-relative bases. Storage-backed and fallback static
branches both require coverage.

## Dependency direction and boundaries

```text
WSGI/ASGI handler -> django.urls request-local prefix state
                                  ^
                                  |
template static/media tags -> private URL-prefix adapter -> URL parsing
          |
          +-> staticfiles storage (opaque complete URL producer)
```

The dependency does not point from `django.urls`, settings, or storage back to
template tags. No public setting, storage contract, discovery behavior, or
serving behavior changes. Context-processor values and URL generation outside
the static/media template-tag flow remain outside this issue.

## Implementation readiness

The implementation delta is confined to one private adapter and two existing
return seams in `django/templatetags/static.py`, followed by conversion of the
six placeholders in `tests/template_tests/syntax_tests/test_static.py`. Every
traced obligation therefore has an owner, integration point, dependency
direction, and verification locus without adding a public API.
