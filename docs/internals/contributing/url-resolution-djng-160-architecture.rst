DJNG-160 Architecture (Yesod)
=============================

Scope
-----
Issue ``DJNG-160`` covers optional named capture handling in ``re_path`` resolution and callback
arity for the route family ``^module/(?P<format>(html|json|xml))?/?$``.

Requirement-to-architecture map
------------------------------
The following obligations are bound to seams and ownership points:

* ``DJNG-001`` is owned by ``django/urls/resolvers.py`` in ``RegexPattern.match`` and
  ``URLPattern.resolve``.
* ``DJNG-002`` is owned by ``django/urls/resolvers.py`` in ``RegexPattern.match``,
  ``URLPattern.resolve``, and ``URLResolver.resolve``; ``BaseHandler._get_response`` is the
  final invocation sink for the unchanged positional/keyword contract.
* ``DJNG-004`` is owned by ``django/core/handlers/base.py`` in ``BaseHandler._get_response`` and
  ``django/urls/resolvers.py`` in ``URLPattern.resolve``.
* ``DJNG-005`` is owned by ``django/urls/resolvers.py`` in ``RegexPattern.match`` and
  ``URLResolver.resolve``.

Placement and boundaries
------------------------
* Capture extraction boundary
  ``RegexPattern.match`` owns regex matching and normalization of captures.
* Pattern binding boundary
  ``URLPattern.resolve`` owns callback argument materialization and default argument merge policy.
* Inclusion boundary
  ``URLResolver.resolve`` owns namespace/default kwargs merge and parent/child arg propagation.
* Optional capture boundary
  The optional named capture path is bounded by ``RegexPattern.match`` and ``URLPattern.resolve``:
  matched tokens become named kwargs and are not reclassified as positional args.
* Invocation boundary
  ``BaseHandler._get_response`` owns final callback signature invocation from resolved args/kwargs.

Contract surfaces
-----------------
* ``RegexPattern.match(path) -> (remaining_path, callback_args, callback_kwargs)``.
* ``URLPattern.resolve(path) -> ResolverMatch(callback, callback_args, callback_kwargs, route_info...)``.
* ``URLResolver.resolve(path) -> ResolverMatch`` with deterministic merge behavior:
  parent kwargs and defaults merge before child kwargs; positional propagation depends on merged kwargs.
* ``BaseHandler._get_response`` consumes ``callback_args`` and ``callback_kwargs`` as disjoint channels
  (non-named positionals and named/defaulted captures).
* ``Callback binding invariant (DJNG-002)``
  if a named optional capture is matched (for example ``format=html|json|xml``), it is injected into
  kwargs through the same capture merge path and does not alter ``callback_args`` cardinality.

Dependency direction
--------------------
1. ``URLResolver.resolve`` delegates to ``pattern.match`` and then to child ``pattern.resolve``.
2. ``URLPattern.resolve`` merges only named capture/kwargs; it does not alter callback arity via positionals.
3. ``BaseHandler._get_response`` applies ``wrapped_callback(request, *callback_args, **callback_kwargs)`` only.

Integration seams and adaptation
-------------------------------
* Seam: ``re_path`` capture extraction semantics in ``RegexPattern.match``.
* Seam: parent/child context merge in ``URLResolver.resolve``.
* Seam: callback arity contract in ``BaseHandler._get_response``.
* Seam: route declaration/behavioral contract at ``tests/urlpatterns.path_urls`` and
  ``tests/urlpatterns.views.modules`` for ``^module/(?P<format>(html|json|xml))?/?$``.

Structural placeholders in scope
-------------------------------
* Tests for traceability live in ``tests/urlpatterns/tests.py``:
  ``test_djng_001_unmatched_optional_named_capture_does_not_become_positional``,
  ``test_djng_002_matched_optional_capture_html_resolves_without_positional_arity_change``,
  ``test_djng_002_matched_optional_capture_json_resolves_without_positional_arity_change``,
  ``test_djng_002_matched_optional_capture_xml_resolves_without_positional_arity_change``,
  ``test_djng_004_optional_capture_with_default_is_not_forced_to_positional_arity``,
  ``test_djng_005_module_route_resolves_default_and_allowed_token_variants``.
* Callback surface for route behavior remains ``tests/urlpatterns.views.modules``.
* Route registration for the regression shape remains ``tests/urlpatterns.path_urls``.

Completion status
-----------------
Architecture-ready for implementation because:

* Every obligation maps to a concrete owner and integration seam.
* Callback binding and merge behavior are separated into distinct modules and methods with explicit contracts.
* Structural artifacts are traceable to ``DJNG-001``, ``DJNG-002``, ``DJNG-004``, and ``DJNG-005``.
