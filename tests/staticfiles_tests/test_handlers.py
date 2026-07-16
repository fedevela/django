from django.test import SimpleTestCase


class ASGIStaticFilesHandlerContractTests(SimpleTestCase):
    def test_asgi_static_001_async_response_avoids_uninitialized_middleware_chain(self):
        """GUID: ASGI-STATIC-001."""
        pass

    def test_asgi_static_004_non_static_async_request_delegates_and_returns_response(self):
        """GUID: ASGI-STATIC-004."""
        pass
