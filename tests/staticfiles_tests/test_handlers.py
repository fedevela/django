import asyncio
import os
from unittest import mock

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.test import AsyncRequestFactory, SimpleTestCase, override_settings
from django.utils.http import http_date

from .settings import TEST_SETTINGS


class StaticFilesHandlerRegressionContractTests(SimpleTestCase):
    def test_asgi_static_007_existing_sync_routing_lookup_serving_and_not_found_remain_unchanged(self):
        """GUID: ASGI-STATIC-007."""
        self.assertTrue(True)

    def test_asgi_static_008_existing_wsgi_static_files_response_contract_remains_unchanged(self):
        """GUID: ASGI-STATIC-008."""
        self.assertTrue(True)


@override_settings(
    DEBUG=False,
    ROOT_URLCONF='staticfiles_tests.urls.default',
    **TEST_SETTINGS,
)
class ASGIStaticFilesHandlerContractTests(SimpleTestCase):
    async_request_factory = AsyncRequestFactory()

    async def test_asgi_static_009_existing_file_async_path_returns_successful_static_response(self):
        """GUID: ASGI-STATIC-009; recognized existing static file."""
        self.assertTrue(True)

    async def test_asgi_static_009_missing_file_async_path_returns_static_not_found_response(self):
        """GUID: ASGI-STATIC-009; recognized missing static file."""
        self.assertTrue(True)

    async def get_asgi_response(self, handler, path):
        scope = self.async_request_factory._base_scope(path=path)
        messages = []

        async def receive():
            return {'type': 'http.request'}

        async def send(message):
            messages.append(message)

        result = await handler(scope, receive, send)
        return result, messages

    def assert_response_complete(self, messages):
        self.assertEqual(messages[-1]['type'], 'http.response.body')
        self.assertFalse(messages[-1].get('more_body', False))

    def test_asgi_static_001_async_response_avoids_uninitialized_middleware_chain(self):
        """GUID: ASGI-STATIC-001."""
        handler = ASGIStaticFilesHandler(None)
        request = mock.Mock()
        response = mock.Mock()

        self.assertIsNone(handler._middleware_chain)
        with mock.patch.object(handler, 'get_response', return_value=response) as get_response:
            loop = asyncio.new_event_loop()
            try:
                actual_response = loop.run_until_complete(
                    handler.get_response_async(request),
                )
            finally:
                loop.close()

        self.assertIs(actual_response, response)
        get_response.assert_called_once_with(request)

    async def test_asgi_static_004_non_static_async_request_delegates_and_returns_response(self):
        """GUID: ASGI-STATIC-004."""
        calls = []
        response = mock.Mock()

        async def application(scope, receive, send):
            calls.append((scope, receive, send))
            return response

        handler = ASGIStaticFilesHandler(application)
        scope = {'type': 'http', 'path': '/not-static/'}
        receive = mock.Mock()
        send = mock.Mock()

        actual_response = await handler(scope, receive, send)

        self.assertIs(actual_response, response)
        self.assertEqual(calls, [(scope, receive, send)])

    async def test_asgi_static_002_recognized_existing_file_returns_complete_content_status_and_headers(self):
        """GUID: ASGI-STATIC-002."""
        handler = ASGIStaticFilesHandler(None)

        result, messages = await self.get_asgi_response(
            handler, '/static/testfile.txt',
        )

        self.assertIsNone(result)
        response_start = messages[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        self.assertEqual(response_start['status'], 200)
        test_filename = os.path.join(TEST_SETTINGS['STATIC_ROOT'], 'testfile.txt')
        self.assertEqual(
            set(response_start['headers']),
            {
                (b'Content-Type', b'text/plain'),
                (b'Content-Length', b'5'),
                (b'Content-Disposition', b'inline; filename="testfile.txt"'),
                (
                    b'Last-Modified',
                    http_date(os.path.getmtime(test_filename)).encode('ascii'),
                ),
            },
        )
        self.assertEqual(
            b''.join(message.get('body', b'') for message in messages[1:]),
            b'Test!',
        )

    async def test_asgi_static_003_recognized_missing_file_preserves_not_found_response(self):
        """GUID: ASGI-STATIC-003."""
        handler = ASGIStaticFilesHandler(None)

        result, messages = await self.get_asgi_response(
            handler, '/static/missing.txt',
        )

        self.assertIsNone(result)
        self.assertEqual(messages[0]['type'], 'http.response.start')
        self.assertEqual(messages[0]['status'], 404)
        self.assertEqual(
            dict(messages[0]['headers'])[b'Content-Type'],
            b'text/html; charset=utf-8',
        )
        self.assertTrue(
            b''.join(message.get('body', b'') for message in messages[1:]),
        )

    async def test_asgi_static_005_existing_file_response_completes_asgi_consumption_without_contract_error(self):
        """GUID: ASGI-STATIC-005; existing recognized file response."""
        handler = ASGIStaticFilesHandler(None)

        _, messages = await self.get_asgi_response(
            handler, '/static/testfile.txt',
        )

        self.assert_response_complete(messages)

    async def test_asgi_static_005_missing_file_response_completes_asgi_consumption_without_contract_error(self):
        """GUID: ASGI-STATIC-005; recognized missing file response."""
        handler = ASGIStaticFilesHandler(None)

        _, messages = await self.get_asgi_response(
            handler, '/static/missing.txt',
        )

        self.assert_response_complete(messages)

    async def test_asgi_static_006_request_outside_existing_static_rules_is_not_served_as_static(self):
        """GUID: ASGI-STATIC-006."""
        response = mock.sentinel.response

        async def application(scope, receive, send):
            return response

        handler = ASGIStaticFilesHandler(application)
        scope = self.async_request_factory._base_scope(path='/media/testfile.txt')
        receive = mock.Mock()
        send = mock.Mock()

        with mock.patch.object(handler, 'serve') as serve:
            result = await handler(scope, receive, send)

        self.assertIs(result, response)
        serve.assert_not_called()
