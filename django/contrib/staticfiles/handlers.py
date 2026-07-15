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
        # Static middleware intentionally reuses the app-level middleware chain.
        # Keep this no-op placeholder to match the StaticFilesHandler mixin API.
        super().__init__()

    # ASGI-001 trace map -> tests:
    # - ASGIStaticFilesHandler.get_response_async_resolves_to_callable
    # - ASGIStaticFilesHandler_dispatch_invokes_resolved_async_callable_once
    async def __call__(self, scope, receive, send):
        # Only even look at HTTP requests
        if scope['type'] == 'http' and self._should_handle(scope['path']):
            # Serve static content
            # (the one thing super() doesn't do is __call__, apparently)
            return await super().__call__(scope, receive, send)
        # Hand off to the main app
        return await self.application(scope, receive, send)

    async def get_response_async(self, request):
        """
        ASGI dispatch path for static files.

        This bypasses middleware resolution so this handler always returns a
        concrete HttpResponse for static paths instead of resolving a URL view.
        """
        return self.get_response(request)
