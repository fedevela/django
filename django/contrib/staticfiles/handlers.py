from urllib.parse import urlparse
from urllib.request import url2pathname

from django.conf import settings
from django.contrib.staticfiles import utils
from django.contrib.staticfiles.views import serve
from django.core.handlers.asgi import ASGIHandler
from django.core.handlers.exception import response_for_exception
from django.core.handlers.wsgi import WSGIHandler, get_path_info
from django.http import Http404


class StaticFilesHandlerMixin:
    """
    Common methods used by WSGI and ASGI handlers.
    """
    # May be used to differentiate between handler types (e.g. in a
    # request_finished signal)
    handles_files = True

    def load_middleware(self):
        # Middleware are already loaded for self.application; no need to reload
        # them for self.
        pass

    def get_base_url(self):
        utils.check_settings()
        return settings.STATIC_URL

    def _should_handle(self, path):
        """
        Check if the path should be handled. Ignore the path if:
        * the host is provided as part of the base_url
        * the request's path isn't under the media path (or equal)
        """
        return path.startswith(self.base_url[2]) and not self.base_url[1]

    def file_path(self, url):
        """
        Return the relative path to the media file on disk for the given URL.
        """
        relative_url = url[len(self.base_url[2]):]
        return url2pathname(relative_url)

    def serve(self, request):
        """Serve the request path."""
        return serve(request, self.file_path(request.path), insecure=True)

    def get_response(self, request):
        try:
            return self.serve(request)
        except Http404 as e:
            return response_for_exception(request, e)


class StaticFilesHandler(StaticFilesHandlerMixin, WSGIHandler):
    """
    WSGI middleware that intercepts calls to the static files directory, as
    defined by the STATIC_URL setting, and serves those files.
    """
    def __init__(self, application):
        self.application = application
        self.base_url = urlparse(self.get_base_url())
        super().__init__()

    def __call__(self, environ, start_response):
        if not self._should_handle(get_path_info(environ)):
            return self.application(environ, start_response)
        return super().__call__(environ, start_response)


class ASGIStaticFilesHandler(StaticFilesHandlerMixin, ASGIHandler):
    """
    ASGI application which wraps another and intercepts requests for static
    files, passing them off to Django's static file serving.

    ASGI-001:
    - get_response_async must resolve to an invocable async callable before
      Django's ASGI dispatch path runs.
    - the resolved async callable must be awaited and invoked exactly once for a
      single static request.
    """
    # ASGI-001: Contractual state model.
    # - base_url is derived from STATIC_URL and determines static-path matching.
    # - application is the wrapped downstream ASGI app for non-static paths.
    # - ASGIHandler.__call__ requires a callable async response entrypoint.
    #   if get_response_async resolves to None, TypeError is raised before
    #   response generation.
    def __init__(self, application):
        self.application = application
        self.base_url = urlparse(self.get_base_url())
        # ASGI-001: Deterministic initialization requirement:
        # - ensure static-handler has an async response invocation path available
        #   and registered before handling the first request.
        # - this is currently the owning artifact point for resolving the failure
        #   mode where ASGI pipeline dereferences None.

    # ASGI-001 trace map -> tests:
    # - ASGIStaticFilesHandler.get_response_async_resolves_to_callable
    # - ASGIStaticFilesHandler_dispatch_invokes_resolved_async_callable_once
    async def __call__(self, scope, receive, send):
        # ASGI-001: Async dispatch decision + call target obligations.
        # Inputs:
        # - scope['type']: expected to be "http" for request handling
        # - scope['path']: candidate path for static file match
        # - self._should_handle(scope['path']): static path predicate
        #
        # Control flow:
        # 1) Only HTTP scopes participate.
        # 2) If HTTP + static path:
        #    a) The static dispatch path must go through an async response
        #       callable (`self.get_response_async`) and be awaited once.
        #    b) `await super().__call__(scope, receive, send)` executes that path.
        # 3) Else:
        #    a) delegate to wrapped downstream app exactly once.
        # Error/failure paths:
        # - if the resolved response callable is not callable/awaitable, fail in
        #   ASGIHandler.__call__ with the NoneType callable pathway.
        # Only even look at HTTP requests
        if scope['type'] == 'http' and self._should_handle(scope['path']):
            # Serve static content
            # (the one thing super() doesn't do is __call__, apparently)
            return await super().__call__(scope, receive, send)
        # Hand off to the main app
        return await self.application(scope, receive, send)

    # ASGI-001:
    # get_response_async (to be implemented in the next phase) is the required
    # async callable slot that ASGIHandler.__call__ invokes.
    # Pseudocode contract to encode during implementation:
    # async def get_response_async(request):
    #   # 1) Build/obtain request-bound context for static dispatch.
    #   # 2) Resolve static response by delegating to self.get_response(request).
    #   # 3) Ensure the result is an HttpResponse instance and return it.
    #   # 4) Preserve single await boundary (exactly one invocation for this
    #      request in __call__ route).
