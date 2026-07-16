# Issue 335: filesystem storage media URL architecture

## Architectural decision

`FileSystemStorage.url(name)` is the ownership boundary for applying the
active request's script prefix when, and only when, the storage URL base is
derived from `settings.MEDIA_URL`. It first completes the existing media-base
and requested-file composition, then adapts that complete application-relative
URL before returning it.

URL-base provenance is represented by the existing constructor state:
`self._base_url is None` means that the effective `base_url` comes from
`settings.MEDIA_URL`; a non-`None` value means that the caller supplied the
base explicitly. Prefix adaptation must use this provenance marker rather than
compare URL strings. The storage instance must not cache a request, script
prefix, or prefixed URL.

## Requirement-to-architecture map

| Requirement | Architecture pressure | Architectural home |
| --- | --- | --- |
| `SCRIPTURL-006` | A non-empty request prefix must occur exactly once before an application-relative, media-derived base while the requested file path remains subordinate to that base. | `FileSystemStorage.url(name)` composes the existing complete URL, then adapts its path only when `self._base_url is None`. |
| `SCRIPTURL-006` | Empty, absent, and root-equivalent request state must preserve current output. | The adaptation seam returns the composed URL unchanged unless `get_script_prefix()` supplies a non-root prefix. |
| `SCRIPTURL-006` | A long-lived storage object must not leak one request's prefix into another request. | `FileSystemStorage.url(name)` reads request-local prefix state once per invocation and stores none of it on the instance. |

## Placement and ownership

### `django/core/files/storage.py`

Keep the change inside `FileSystemStorage.url(name)`, immediately after its
existing `filepath_to_uri()` and `urljoin()` composition. Its implementation
contract is:

- preserve the existing inaccessible-file error, filename encoding, leading
  separator handling, and base/path joining;
- treat `self._base_url is None` as the sole signal that the effective base is
  derived from `MEDIA_URL`;
- return explicitly based storage URLs unchanged, even if their string value
  happens to equal `settings.MEDIA_URL`;
- return absolute and protocol-relative composed URLs unchanged;
- read `django.urls.get_script_prefix()` at call time, retaining no
  request-local state;
- return the composed URL unchanged for an absent, empty, or root prefix;
- return it unchanged when its path already starts with the complete active
  prefix on a path-segment boundary;
- otherwise insert the prefix before the complete media base, preserving the
  requested file path plus any query or fragment data; and
- propagate existing encoding, joining, parsing, and reconstruction failures
  without returning or caching a partial result.

URL parsing and reconstruction remain private implementation details of this
method. No new method is added to the public `Storage` interface, and no
request object enters the storage API.

### `django/urls/base.py`

No structural change is required. `set_script_prefix()`,
`get_script_prefix()`, and `clear_script_prefix()` remain the request-local
lifecycle port populated by the WSGI and ASGI handlers. Core file storage has
a read-only, per-call dependency on the public getter.

### `django/contrib/staticfiles/storage.py`

No structural change is required. `StaticFilesStorage.__init__()` passes its
`STATIC_URL` value explicitly to `FileSystemStorage`, so its inherited
`self._base_url` is non-`None`. The new core media seam therefore leaves the
inherited candidate unchanged, and `StaticFilesStorage.url(name)` remains the
sole storage owner of static-prefix adaptation.

### `tests/file_storage/tests.py`

`ScriptNameFileSystemStorageContractTests` is the traced verification seam.
During implementation its three placeholders become behavioral tests that:

1. instantiate media-derived `FileSystemStorage`, apply a non-empty prefix,
   and assert exact-once ordering of prefix, media base, and requested path;
2. verify absent, empty, and root-equivalent prefixes against the existing
   unprefixed output; and
3. reuse one storage instance across different script-prefix contexts and
   assert that each result contains only its invocation's prefix.

The first test should also call `url()` twice in one prefixed context, proving
that exact-once behavior does not depend on mutating `base_url`.

## Dependency direction and integration seams

```text
WSGI/ASGI handler -> django.urls request-local prefix state
                                  ^
                                  |
                    FileSystemStorage.url(name)
                       |                    |
                       |                    +-> read prefix per call
                       v
filename -> URI encoding -> MEDIA_URL join -> complete media URL
                                              |
                                              v
                                  conditional path adaptation
                                              |
                                              v
                                     returned file URL

StaticFilesStorage -- explicit STATIC_URL --> FileSystemStorage
       |                                      (media seam bypassed)
       +------------------------------------> static prefix adaptation
```

The dependency remains one-way: storage reads URL-prefix state;
`django.urls` does not depend on storage. Settings remain configuration input,
not a holder of request-local state. The filesystem path, saved name, and file
contents do not participate in this URL-presentation seam.

## Preserved boundaries

This architecture changes only URL presentation for default, media-derived
`FileSystemStorage` bases. It does not alter storage contents, naming,
filesystem paths, discovery, uploads, or serving. Explicit `base_url` values
remain caller-owned, and no public configuration or storage interface is
introduced.

## Implementation readiness

`SCRIPTURL-006` has one concrete owner, a provenance boundary, a request-state
port, an integration seam, and a traced verification locus. Implementation is
confined to `FileSystemStorage.url(name)` and the three behavioral tests in
`tests/file_storage/tests.py`; no public API or file topology expansion is
required.
