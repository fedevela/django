import inspect

from unittest.mock import Mock

from asgiref.testing import ApplicationCommunicator
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.handlers.asgi import ASGIHandler
from django.http import HttpRequest, HttpResponse
from django.test import AsyncRequestFactory, SimpleTestCase, override_settings


# Contract map (canonical IDs -> verification obligations).
REQUIREMENT_VERIFICATION_MAP = {
    "ASGI-001": [
        "ASGIStaticFilesHandler.get_response_async_resolves_to_callable",
        "ASGIStaticFilesHandler_dispatch_invokes_resolved_async_callable_once",
    ],
}


class ASGIStaticFilesHandlerTraceabilityTests(SimpleTestCase):
    """ASGI-001: traceability and behavior checks for staticfiles async dispatch."""
    async_request_factory = AsyncRequestFactory()

    async_test_target = ASGIHandler
    asgi_static_handler = ASGIStaticFilesHandler

    async def test_asgi_001_get_response_async_is_non_none_and_awaitable(self):
        # Obligation ASGI-001: ensure the async response callable slot is present.
        handler = ASGIStaticFilesHandler(application=self._passthrough_app)
        handler.get_response = Mock(return_value=HttpResponse("ok", content_type="text/plain"))
        request = HttpRequest()
        request.path = "/static/file.txt"
        response_coroutine = handler.get_response_async(request)

        self.assertIsNotNone(response_coroutine)
        self.assertTrue(inspect.isawaitable(response_coroutine))
        response = await response_coroutine
        self.assertIsInstance(response, HttpResponse)

    @override_settings(STATIC_URL="/static/")
    async def test_asgi_001_middleware_chain_invoked_once_via_ASGIHandler_call(self):
        # Obligation ASGI-001: ensure invocation target stability for async dispatch.
        handler = ASGIStaticFilesHandler(application=self._passthrough_app)
        handler.get_response = Mock(return_value=HttpResponse("ok", content_type="text/plain"))
        communicator = ApplicationCommunicator(
            handler,
            self.async_request_factory._base_scope(path="/static/file.txt"),
        )
        await communicator.send_input({"type": "http.request"})

        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"ok")
        self.assertEqual(handler.get_response.call_count, 1)
        await communicator.wait()

    async def _passthrough_app(self, scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b"passthrough"})
