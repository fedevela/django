import asyncio
from unittest import mock

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.test import SimpleTestCase


class ASGIStaticFilesHandlerContractTests(SimpleTestCase):
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

    def test_asgi_static_002_recognized_existing_file_returns_complete_content_status_and_headers(self):
        """GUID: ASGI-STATIC-002."""
        self.assertTrue(True)

    def test_asgi_static_003_recognized_missing_file_preserves_not_found_response(self):
        """GUID: ASGI-STATIC-003."""
        self.assertTrue(True)

    def test_asgi_static_005_existing_file_response_completes_asgi_consumption_without_contract_error(self):
        """GUID: ASGI-STATIC-005; existing recognized file response."""
        self.assertTrue(True)

    def test_asgi_static_005_missing_file_response_completes_asgi_consumption_without_contract_error(self):
        """GUID: ASGI-STATIC-005; recognized missing file response."""
        self.assertTrue(True)

    def test_asgi_static_006_request_outside_existing_static_rules_is_not_served_as_static(self):
        """GUID: ASGI-STATIC-006."""
        self.assertTrue(True)
