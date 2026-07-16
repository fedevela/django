# Issue 334: staticfiles request-prefix URL architecture

## Architectural decision

`StaticFilesStorage.url(name)` is the ownership boundary for applying the
active request's script prefix to URLs generated from `STATIC_URL`. It first
delegates the existing base-and-asset composition to
`FileSystemStorage.url(name)`, then adapts that complete URL before returning
it. The storage instance does not retain a request or prefix.

This is a narrow extension of the request-state boundary established for the
default static tag. `django.urls` continues to own request-local prefix state;
`StaticFilesStorage` may read that state at URL-generation time but must not
write it. Core `Storage` and `FileSystemStorage` remain request-independent.

## Requirement-to-architecture map

| Requirement | Architecture pressure | Architectural home |
| --- | --- | --- |
| `SCRIPTURL-005` | Every URL-generation entry through `django.contrib.staticfiles` must receive an active non-root prefix exactly once, while absent, empty, and root-equivalent prefixes preserve existing output. | `StaticFilesStorage.url(name)` adapts its complete inherited result. The default static tag may pass that result through its own idempotent adapter without adding the same prefix twice. |
| `SCRIPTURL-007` | Prefix adaptation must occur outside the configured static base and requested asset path, without changing their relationship. | `FileSystemStorage.url(name)` remains the sole base-and-path composer; `StaticFilesStorage.url(name)` applies the active prefix only after that composition is complete. |

## Placement and ownership

### `django/contrib/staticfiles/storage.py`

Add a `StaticFilesStorage.url(name)` override beside `path(name)`. Its
structural contract is:

- obtain one complete candidate URL from `super().url(name)`;
- return absolute and protocol-relative candidates unchanged;
- read the current script prefix for each call and retain no request-local
  state on the storage instance;
- return the candidate unchanged for an absent, empty, or root prefix;
- return the candidate unchanged when its path already begins with the full
  active prefix on a path-segment boundary;
- otherwise insert the prefix before the complete configured static base,
  preserving the subordinate asset path, query, and fragment; and
- propagate inherited URL-generation and parsing failures without returning a
  partial URL.

The override must not reimplement `filepath_to_uri()`, `urljoin()`, base URL
selection, or asset-path normalization. Those remain owned by
`FileSystemStorage.url(name)`. It also must not change `path()`, discovery,
collection, post-processing, file contents, or serving.

`HashedFilesMixin._url()` already calls `super().url(hashed_name)`. Under the
existing `ManifestStaticFilesStorage` method-resolution order, that call
enters `StaticFilesStorage.url(name)`, so hashed and manifest URLs receive the
same prefix boundary without another override. Hash selection remains owned by
the mixin, and its existing fragment restoration remains downstream of the
storage prefix adaptation.

### `django/templatetags/static.py`

No structural change is required for this issue. `StaticNode.handle_simple()`
continues to treat storage output as a complete candidate and pass it through
its private request-prefix adapter. Because both the storage and tag contracts
recognize an already-prefixed path on a segment boundary, their composition is
idempotent. The tag-level seam remains necessary for custom storage backends
and for the no-staticfiles fallback; the storage-level seam is necessary for
direct `StaticFilesStorage.url()` callers.

### `tests/staticfiles_tests/test_storage.py`

`ScriptNameStaticFilesStorageContractTests` is the traced verification seam.
During implementation, its four placeholders should become behavioral tests
that cover:

1. a non-empty prefix appearing exactly once in staticfiles-generated output;
2. absent, empty, and root-equivalent prefixes preserving existing output;
3. the configured static base and requested asset path remaining ordered
   beneath a non-empty prefix; and
4. direct `StaticFilesStorage.url()` compatibility for absent, empty, and root
   prefix state.

Tests should use `override_script_prefix` so sequential calls demonstrate that
the storage object does not cache request state. At least one path should enter
through `staticfiles_storage` and one should instantiate or subclass
`StaticFilesStorage` directly, preserving the distinction between
`SCRIPTURL-005` and `SCRIPTURL-007`.

## Dependency direction and integration seams

```text
WSGI/ASGI handler -> django.urls request-local prefix state
                                  ^
                                  |
                       StaticFilesStorage.url(name)
                                  ^
                                  |
HashedFilesMixin._url() -> super().url(hashed_name)

requested asset -> FileSystemStorage.url(name) -> complete static URL
                                                    |
                                                    v
                                      storage prefix adaptation
                                                    |
                                                    v
                                      optional tag adaptation
                                      (exact-once/idempotent)
```

The dependency on request-local state is confined to
`django.contrib.staticfiles.storage`; it does not descend into
`django.core.files.storage`. `django.urls` does not depend on staticfiles, and
neither storage layer depends on template rendering. The template tag remains
a downstream consumer of an opaque complete storage URL.

## Preserved boundaries

This architecture changes URL presentation only. It does not alter static-file
discovery, collection, storage contents, hashing, post-processing, or serving.
It does not require custom storage transformations and the default template
tag to be byte-for-byte identical; each seam independently preserves the
`SCRIPTURL-001` prefix contract.

## Implementation readiness

Both requirements have a concrete owner, integration seam, dependency
direction, and traced verification locus. The implementation delta is confined
to the `StaticFilesStorage.url(name)` override and conversion of the four
placeholders in `tests/staticfiles_tests/test_storage.py`; no public API or
topology expansion is required.
