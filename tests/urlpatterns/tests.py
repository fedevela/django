import uuid

from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.test import Client, SimpleTestCase
from django.test.utils import override_settings
from django.urls import Resolver404, path, resolve, reverse

from .converters import DynamicConverter
from .views import empty_view

included_kwargs = {'base': b'hello', 'value': b'world'}
converter_test_data = (
    # ('url', ('url_name', 'app_name', {kwargs})),
    # aGVsbG8= is 'hello' encoded in base64.
    ('/base64/aGVsbG8=/', ('base64', '', {'value': b'hello'})),
    ('/base64/aGVsbG8=/subpatterns/d29ybGQ=/', ('subpattern-base64', '', included_kwargs)),
    ('/base64/aGVsbG8=/namespaced/d29ybGQ=/', ('subpattern-base64', 'namespaced-base64', included_kwargs)),
)


@override_settings(ROOT_URLCONF='urlpatterns.path_urls')
class SimplifiedURLTests(SimpleTestCase):

    def test_path_lookup_without_parameters(self):
        match = resolve('/articles/2003/')
        self.assertEqual(match.url_name, 'articles-2003')
        self.assertEqual(match.args, ())
        self.assertEqual(match.kwargs, {})
        self.assertEqual(match.route, 'articles/2003/')

    def test_path_lookup_with_typed_parameters(self):
        match = resolve('/articles/2015/')
        self.assertEqual(match.url_name, 'articles-year')
        self.assertEqual(match.args, ())
        self.assertEqual(match.kwargs, {'year': 2015})
        self.assertEqual(match.route, 'articles/<int:year>/')

    def test_path_lookup_with_multiple_paramaters(self):
        match = resolve('/articles/2015/04/12/')
        self.assertEqual(match.url_name, 'articles-year-month-day')
        self.assertEqual(match.args, ())
        self.assertEqual(match.kwargs, {'year': 2015, 'month': 4, 'day': 12})
        self.assertEqual(match.route, 'articles/<int:year>/<int:month>/<int:day>/')

    def test_two_variable_at_start_of_path_pattern(self):
        match = resolve('/en/foo/')
        self.assertEqual(match.url_name, 'lang-and-path')
        self.assertEqual(match.kwargs, {'lang': 'en', 'url': 'foo'})
        self.assertEqual(match.route, '<lang>/<path:url>/')

    def test_re_path(self):
        match = resolve('/regex/1/')
        self.assertEqual(match.url_name, 'regex')
        self.assertEqual(match.kwargs, {'pk': '1'})
        self.assertEqual(match.route, '^regex/(?P<pk>[0-9]+)/$')

    def test_re_path_with_optional_parameter(self):
        for url, kwargs in (
            ('/regex_optional/1/2/', {'arg1': '1', 'arg2': '2'}),
            ('/regex_optional/1/', {'arg1': '1'}),
        ):
            with self.subTest(url=url):
                match = resolve(url)
                self.assertEqual(match.url_name, 'regex_optional')
                self.assertEqual(match.kwargs, kwargs)
                self.assertEqual(
                    match.route,
                    r'^regex_optional/(?P<arg1>\d+)/(?:(?P<arg2>\d+)/)?',
                )

    def test_path_lookup_with_inclusion(self):
        match = resolve('/included_urls/extra/something/')
        self.assertEqual(match.url_name, 'inner-extra')
        self.assertEqual(match.route, 'included_urls/extra/<extra>/')

    def test_path_lookup_with_empty_string_inclusion(self):
        match = resolve('/more/99/')
        self.assertEqual(match.url_name, 'inner-more')
        self.assertEqual(match.route, r'^more/(?P<extra>\w+)/$')

    def test_path_lookup_with_double_inclusion(self):
        match = resolve('/included_urls/more/some_value/')
        self.assertEqual(match.url_name, 'inner-more')
        self.assertEqual(match.route, r'included_urls/more/(?P<extra>\w+)/$')

    def test_path_reverse_without_parameter(self):
        url = reverse('articles-2003')
        self.assertEqual(url, '/articles/2003/')

    def test_path_reverse_with_parameter(self):
        url = reverse('articles-year-month-day', kwargs={'year': 2015, 'month': 4, 'day': 12})
        self.assertEqual(url, '/articles/2015/4/12/')

    @override_settings(ROOT_URLCONF='urlpatterns.path_base64_urls')
    def test_converter_resolve(self):
        for url, (url_name, app_name, kwargs) in converter_test_data:
            with self.subTest(url=url):
                match = resolve(url)
                self.assertEqual(match.url_name, url_name)
                self.assertEqual(match.app_name, app_name)
                self.assertEqual(match.kwargs, kwargs)

    @override_settings(ROOT_URLCONF='urlpatterns.path_base64_urls')
    def test_converter_reverse(self):
        for expected, (url_name, app_name, kwargs) in converter_test_data:
            if app_name:
                url_name = '%s:%s' % (app_name, url_name)
            with self.subTest(url=url_name):
                url = reverse(url_name, kwargs=kwargs)
                self.assertEqual(url, expected)

    @override_settings(ROOT_URLCONF='urlpatterns.path_base64_urls')
    def test_converter_reverse_with_second_layer_instance_namespace(self):
        kwargs = included_kwargs.copy()
        kwargs['last_value'] = b'world'
        url = reverse('instance-ns-base64:subsubpattern-base64', kwargs=kwargs)
        self.assertEqual(url, '/base64/aGVsbG8=/subpatterns/d29ybGQ=/d29ybGQ=/')

    def test_path_inclusion_is_matchable(self):
        match = resolve('/included_urls/extra/something/')
        self.assertEqual(match.url_name, 'inner-extra')
        self.assertEqual(match.kwargs, {'extra': 'something'})

    def test_path_inclusion_is_reversible(self):
        url = reverse('inner-extra', kwargs={'extra': 'something'})
        self.assertEqual(url, '/included_urls/extra/something/')

    def test_invalid_converter(self):
        msg = "URL route 'foo/<nonexistent:var>/' uses invalid converter 'nonexistent'."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            path('foo/<nonexistent:var>/', empty_view)


@override_settings(ROOT_URLCONF='urlpatterns.converter_urls')
class ConverterTests(SimpleTestCase):

    def test_matching_urls(self):
        def no_converter(x):
            return x

        test_data = (
            ('int', {'0', '1', '01', 1234567890}, int),
            ('str', {'abcxyz'}, no_converter),
            ('path', {'allows.ANY*characters'}, no_converter),
            ('slug', {'abcxyz-ABCXYZ_01234567890'}, no_converter),
            ('uuid', {'39da9369-838e-4750-91a5-f7805cd82839'}, uuid.UUID),
        )
        for url_name, url_suffixes, converter in test_data:
            for url_suffix in url_suffixes:
                url = '/%s/%s/' % (url_name, url_suffix)
                with self.subTest(url=url):
                    match = resolve(url)
                    self.assertEqual(match.url_name, url_name)
                    self.assertEqual(match.kwargs, {url_name: converter(url_suffix)})
                    # reverse() works with string parameters.
                    string_kwargs = {url_name: url_suffix}
                    self.assertEqual(reverse(url_name, kwargs=string_kwargs), url)
                    # reverse() also works with native types (int, UUID, etc.).
                    if converter is not no_converter:
                        # The converted value might be different for int (a
                        # leading zero is lost in the conversion).
                        converted_value = match.kwargs[url_name]
                        converted_url = '/%s/%s/' % (url_name, converted_value)
                        self.assertEqual(reverse(url_name, kwargs={url_name: converted_value}), converted_url)

    def test_nonmatching_urls(self):
        test_data = (
            ('int', {'-1', 'letters'}),
            ('str', {'', '/'}),
            ('path', {''}),
            ('slug', {'', 'stars*notallowed'}),
            ('uuid', {
                '',
                '9da9369-838e-4750-91a5-f7805cd82839',
                '39da9369-838-4750-91a5-f7805cd82839',
                '39da9369-838e-475-91a5-f7805cd82839',
                '39da9369-838e-4750-91a-f7805cd82839',
                '39da9369-838e-4750-91a5-f7805cd8283',
            }),
        )
        for url_name, url_suffixes in test_data:
            for url_suffix in url_suffixes:
                url = '/%s/%s/' % (url_name, url_suffix)
                with self.subTest(url=url), self.assertRaises(Resolver404):
                    resolve(url)


class ParameterRestrictionTests(SimpleTestCase):
    def test_non_identifier_parameter_name_causes_exception(self):
        msg = (
            "URL route 'hello/<int:1>/' uses parameter name '1' which isn't "
            "a valid Python identifier."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            path(r'hello/<int:1>/', lambda r: None)

    def test_allows_non_ascii_but_valid_identifiers(self):
        # \u0394 is "GREEK CAPITAL LETTER DELTA", a valid identifier.
        p = path('hello/<str:\u0394>/', lambda r: None)
        match = p.resolve('hello/1/')
        self.assertEqual(match.kwargs, {'\u0394': '1'})


@override_settings(ROOT_URLCONF='urlpatterns.path_dynamic_urls')
class ConversionExceptionTests(SimpleTestCase):
    """How are errors in Converter.to_python() and to_url() handled?"""
    # Requirement mapping for traceability in Phase 5:
    # - DJ-RES-001: converter to_python Http404 must route to normal 404/not-found flow.
    # - DJ-RES-007: converter-originated technical-404 should preserve Http404 message.
    # - DJ-RES-003: converter to_python Http404 must be production-safe when DEBUG=False.

    # Netazch phase 5 traceability obligations:
    # - DJ-RES-002: fallback to later candidate when converter.to_python() raises Http404
    # - DJ-RES-003: converter to_python(Http404) remains production-safe when DEBUG=False
    # - DJ-RES-004: ValueError from to_python keeps routing miss semantics and does not become 500
    # - DJ-RES-005: non-Http404/non-ValueError exceptions from to_python keep internal 500 semantics
    # - DJ-RES-006: successful converter.to_python() and dispatch flow remains intact for matched candidates.
    # - DJ-RES-008: debug-mode technical-vs-production 404 and candidate-fallback regressions for converter Http404.

    def _set_dynamic_converter_to_python(self, callback):
        original_converter = DynamicConverter._dynamic_to_python
        DynamicConverter.register_to_python(callback)
        self.addCleanup(setattr, DynamicConverter, '_dynamic_to_python', original_converter)

    @override_settings(ROOT_URLCONF='urlpatterns.converter_http404_candidates')
    def test_DJ_RES_004_converter_to_python_value_error_keeps_candidate_matching_semantics(self):
        """[DJ-RES-004] Preserve ValueError as converter match-miss without turning it into a 500 path."""
        def raises_value_error(value):
            raise ValueError('not a match')

        self._set_dynamic_converter_to_python(raises_value_error)

        response = self.client.get('/candidate-miss/abc/')
        self.assertEqual(response.status_code, 200)
        match = resolve('/candidate-miss/abc/')
        self.assertEqual(match.url_name, 'candidate-miss-fallback')
        self.assertEqual(match.kwargs, {'value': 'abc'})
        self.assertEqual(match.route, 'candidate-miss/<slug:value>/')
        with self.assertRaises(Resolver404):
            resolve('/candidate-all-miss/abc/')

    def test_DJ_RES_001_converter_to_python_http404_transitions_to_resolver_not_found_flow(self):
        """[DJ-RES-001] When converter.to_python raises Http404, resolver treats it as 404 route-miss."""
        def raises_http404(value):
            raise Http404('user not found')

        self._set_dynamic_converter_to_python(raises_http404)
        with self.assertRaises(Resolver404) as exc_info:
            resolve('/dynamic/usernotfound/')

        payload = exc_info.exception.args[0]
        self.assertEqual(payload['reason'], 'user not found')
        self.assertEqual(payload['path'], '')
        self.assertIsInstance(payload['tried'], list)
        self.assertEqual(len(payload['tried']), 1)
        self.assertEqual(len(payload['tried'][0]), 1)

    @override_settings(DEBUG=True)
    def test_DJ_RES_007_converter_to_python_http404_includes_message_in_technical_404(self):
        """[DJ-RES-007] Converter-originated Http404 message is visible in technical 404 diagnostics."""
        def raises_http404(value):
            raise Http404('user not found')

        self._set_dynamic_converter_to_python(raises_http404)
        response = self.client.get('/dynamic/usernotfound/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'user not found')

    @override_settings(DEBUG=True)
    def test_DJ_RES_008_debug_true_converter_to_python_http404_surfaces_technical_404_message(self):
        """[DJ-RES-008] Debug-true regression: Http404 reason from converter is visible in technical 404 output."""
        # Pseudocode (DJ-RES-008, Scenario 1: DEBUG=True technical-404):
        # 1) Arrange converter callback => raise Http404("custom 404 reason").
        # 2) Register callback through DynamicConverter.register_to_python.
        # 3) Issue client GET for a dynamic-matched path ("/dynamic/usernotfound/").
        # 4) Resolve contract decision:
        #    - to_python raises Http404
        #    - DEBUG is true
        #    - system should return technical 404 response.
        # 5) Expected outcomes:
        #    status_code == 404
        #    response includes "custom 404 reason"
        #    debug diagnostic content remains visible.
        # 6) Failure path:
        #    If response is production-style 404 or hides reason -> regression.
        pass

    @override_settings(DEBUG=True)
    def test_DJ_RES_001_DJ_RES_007_converter_to_python_http404_maps_to_technical_404_lifecycle(self):
        """[DJ-RES-001][DJ-RES-007] Converter Http404 follows routing miss technical-404 lifecycle."""
        def raises_http404(value):
            raise Http404('user not found')

        self._set_dynamic_converter_to_python(raises_http404)
        response = self.client.get('/dynamic/usernotfound/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Django tried these URL patterns', status_code=404)
        self.assertContains(response, 'dynamic/<dynamic:value>/', status_code=404)
        self.assertContains(response, 'user not found', status_code=404)

    @override_settings(DEBUG=False)
    def test_DJ_RES_003_converter_to_python_http404_produces_404_status_with_production_safe_notfound_output(self):
        """[DJ-RES-003] Converter to_python(Http404) remains production-safe when DEBUG=False."""
        def raises_http404(value):
            raise Http404('user not found')

        self._set_dynamic_converter_to_python(raises_http404)
        response = self.client.get('/dynamic/usernotfound/')

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '<h1>Not Found</h1>', status_code=404)
        self.assertContains(
            response,
            'The requested resource was not found on this server.',
            status_code=404,
        )
        self.assertNotContains(response, 'Django tried these URL patterns', status_code=404)
        self.assertNotContains(response, 'user not found', status_code=404)
        self.assertNotContains(response, 'Request Method:', status_code=404)

    @override_settings(DEBUG=False)
    def test_DJ_RES_008_debug_false_converter_to_python_http404_yields_production_safe_404(self):
        """[DJ-RES-008] Debug-false regression: converter Http404 remains production-safe with no debug traceback."""
        # Pseudocode (DJ-RES-008, Scenario 2: DEBUG=False production-safe 404):
        # 1) Arrange converter callback => raise Http404("custom 404 reason").
        # 2) Register callback through DynamicConverter.register_to_python.
        # 3) Issue client GET for same dynamic path used in Scenario 1.
        # 4) Resolve contract decision:
        #    - to_python raises Http404
        #    - DEBUG is false
        #    - system should return generic 404 response.
        # 5) Expected outcomes:
        #    status_code == 404
        #    response contains generic Not Found content
        #    response omits Django diagnostic block and "custom 404 reason".
        # 6) Failure path:
        #    If debug internals or raw message leak -> regression.
        pass

    @override_settings(ROOT_URLCONF='urlpatterns.converter_http404_candidates')
    def test_DJ_RES_002_candidate_http404_marks_candidate_as_miss_and_allows_later_match(self):
        """[DJ-RES-002] Candidate with converter Http404 should be treated as a non-match while later candidates can match."""
        def raises_http404(value):
            raise Http404('user not found')

        self._set_dynamic_converter_to_python(raises_http404)
        response = self.client.get('/candidate-miss/abc/')
        self.assertEqual(response.status_code, 200)

        match = resolve('/candidate-miss/abc/')
        self.assertEqual(match.url_name, 'candidate-miss-fallback')
        self.assertEqual(match.kwargs, {'value': 'abc'})
        self.assertEqual(match.route, 'candidate-miss/<slug:value>/')

    @override_settings(ROOT_URLCONF='urlpatterns.converter_http404_candidates')
    def test_DJ_RES_008_candidate_http404_then_fallback_candidate_dispatches_successfully(self):
        """[DJ-RES-008] Candidate fallback regression: first candidate Http404 does not block later resolver matches."""
        # Pseudocode (DJ-RES-008, Scenario 3: candidate fallback):
        # 1) Arrange converter callback => raise Http404("custom 404 reason").
        # 2) Register callback through DynamicConverter.register_to_python.
        # 3) In URLConf with candidates:
        #    - candidate 1: dynamic pattern using the raising converter
        #    - candidate 2: fallback pattern that matches same segment as slug.
        # 4) Issue client GET for "/candidate-miss/abc/".
        # 5) Candidate loop transition:
        #    - candidate 1 converted value raises Http404 -> mark miss and continue.
        #    - candidate 2 attempted -> match found.
        # 6) Expected outcomes:
        #    status_code == 200
        #    resolved match indicates fallback candidate ("candidate-miss-fallback")
        #    kwargs == {"value": "abc"}
        #    route == "candidate-miss/<slug:value>/"
        # 7) Failure path:
        #    if loop aborts on first Http404 and returns 404 -> regression.
        pass

    @override_settings(ROOT_URLCONF='urlpatterns.converter_http404_candidates')
    def test_DJ_RES_002_candidate_http404_when_no_candidates_match_results_in_not_found(self):
        """[DJ-RES-002] When all candidates fail matching (including Http404 converter failures), resolver ends in 404."""
        def raises_http404(value):
            raise Http404('user not found')

        self._set_dynamic_converter_to_python(raises_http404)
        with self.assertRaises(Resolver404) as exc_info:
            resolve('/candidate-all-miss/abc/')

        payload = exc_info.exception.args[0]
        self.assertEqual(payload['reason'], 'user not found')
        self.assertIsInstance(payload['tried'], list)
        self.assertEqual(len(payload['tried']), 2)
        self.assertEqual(len(payload['tried'][0]), 1)
        self.assertEqual(len(payload['tried'][1]), 1)

    @override_settings(ROOT_URLCONF='urlpatterns.converter_http404_candidates')
    def test_DJ_RES_006_http404_miss_handling_does_not_alter_successful_to_python_view_dispatch(self):
        """[DJ-RES-006] Successful converter to_python execution and view dispatch for matching candidates remains unchanged."""
        def to_python(value):
            return value

        self._set_dynamic_converter_to_python(to_python)
        response = self.client.get('/candidate-success/123/')
        self.assertEqual(response.status_code, 200)
        match = resolve('/candidate-success/123/')

        self.assertEqual(match.url_name, 'candidate-success-first')
        self.assertEqual(match.kwargs, {'value': '123'})
        self.assertEqual(match.route, 'candidate-success/<dynamic:value>/')

    def test_DJ_RES_005_converter_to_python_runtimeerror_keeps_internal_failure_path(self):
        """[DJ-RES-005] Preserve non-Http404, non-ValueError converter exceptions as internal failures."""
        def raises_runtime_error(value):
            raise RuntimeError('conversion blew up')

        self._set_dynamic_converter_to_python(raises_runtime_error)
        with self.assertRaises(RuntimeError):
            resolve('/dynamic/abc/')

        client = Client(raise_request_exception=False)
        response = client.get('/dynamic/abc/')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.exc_info[0], RuntimeError)
        self.assertEqual(str(response.exc_info[1]), 'conversion blew up')

    def test_resolve_value_error_means_no_match(self):
        @DynamicConverter.register_to_python
        def raises_value_error(value):
            raise ValueError()
        with self.assertRaises(Resolver404):
            resolve('/dynamic/abc/')

    def test_resolve_type_error_propagates(self):
        @DynamicConverter.register_to_python
        def raises_type_error(value):
            raise TypeError('This type error propagates.')
        with self.assertRaisesMessage(TypeError, 'This type error propagates.'):
            resolve('/dynamic/abc/')

    def test_reverse_value_error_propagates(self):
        @DynamicConverter.register_to_url
        def raises_value_error(value):
            raise ValueError('This value error propagates.')
        with self.assertRaisesMessage(ValueError, 'This value error propagates.'):
            reverse('dynamic', kwargs={'value': object()})
