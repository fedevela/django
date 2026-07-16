import functools
import re
import sys
import types
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotFound
from django.template import Context, Engine, TemplateDoesNotExist
from django.template.defaultfilters import pprint
from django.urls import resolve
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from django.utils.encoding import force_str
from django.utils.module_loading import import_string
from django.utils.regex_helper import _lazy_re_compile
from django.utils.version import get_docs_version

# Minimal Django templates engine to render the error templates
# regardless of the project's TEMPLATES setting. Templates are
# read directly from the filesystem so that the error handler
# works even if the template loader is broken.
DEBUG_ENGINE = Engine(
    debug=True,
    libraries={'i18n': 'django.templatetags.i18n'},
)

CURRENT_DIR = Path(__file__).parent


class CallableSettingWrapper:
    """
    Object to wrap callable appearing in settings.
    * Not to call in the debug page (#21345).
    * Not to break the debug page if the callable forbidding to set attributes
      (#23070).
    """
    def __init__(self, callable_setting):
        self._wrapped = callable_setting

    def __repr__(self):
        return repr(self._wrapped)


def technical_500_response(request, exc_type, exc_value, tb, status_code=500):
    """
    Create a technical server error response. The last three arguments are
    the values returned from sys.exc_info() and friends.
    """
    reporter = get_exception_reporter_class(request)(request, exc_type, exc_value, tb)
    if request.accepts('text/html'):
        html = reporter.get_traceback_html()
        return HttpResponse(html, status=status_code, content_type='text/html')
    else:
        text = reporter.get_traceback_text()
        return HttpResponse(text, status=status_code, content_type='text/plain; charset=utf-8')


@functools.lru_cache()
def get_default_exception_reporter_filter():
    # Instantiate the default filter for the first time and cache it.
    return import_string(settings.DEFAULT_EXCEPTION_REPORTER_FILTER)()


def get_exception_reporter_filter(request):
    default_filter = get_default_exception_reporter_filter()
    return getattr(request, 'exception_reporter_filter', default_filter)


def get_exception_reporter_class(request):
    default_exception_reporter_class = import_string(settings.DEFAULT_EXCEPTION_REPORTER)
    return getattr(request, 'exception_reporter_class', default_exception_reporter_class)


class SafeExceptionReporterFilter:
    """
    Use annotations made by the sensitive_post_parameters and
    sensitive_variables decorators to filter out sensitive information.
    """
    cleansed_substitute = '********************'
    hidden_settings = _lazy_re_compile('API|TOKEN|KEY|SECRET|PASS|SIGNATURE', flags=re.I)

    # Architecture boundary for SAFE-001, SAFE-002, and SAFE-006:
    # cleanse_setting() owns safe-settings value traversal and reconstruction.
    # get_safe_settings() remains the integration seam that enumerates settings
    # and delegates each value here. Container handling depends inward on this
    # class's existing key matcher and cleansing representation; it must not
    # introduce a second policy surface or expand the public reporter contract.
    def cleanse_setting(self, key, value):
        """
        Cleanse an individual setting key/value of sensitive content. If the
        value is a dictionary, recursively cleanse the keys in that dictionary.
        """
        # Pseudocode obligations for get_safe_settings() nested cleansing:
        #
        # GUID: SAFE-001 - Mask sensitive dictionary entries at any reached level.
        # INPUT a dictionary-entry key and its associated value.
        # IF the existing sensitive-key matcher accepts the key:
        #     RETURN the established cleansed substitute without traversing value.
        # OTHERWISE, delegate value handling to the container decisions below.
        #
        # GUID: SAFE-002 - Traverse every finite combination of supported containers.
        # IF value is a dictionary:
        #     FOR EACH key/value entry, recursively cleanse that entry.
        #     RETURN a dictionary containing the cleansed entries.
        # ELSE IF value is a list:
        #     FOR EACH item, recursively cleanse it with no sensitive entry key.
        #     RETURN a list containing the cleansed items in their original order.
        # ELSE IF value is a tuple:
        #     FOR EACH item, recursively cleanse it with no sensitive entry key.
        #     RETURN a tuple containing the cleansed items in their original order.
        # Each recursive handoff repeats sensitive-key matching before descending.
        #
        # GUID: SAFE-003 - Preserve each non-sensitive scalar value.
        # IF the key is not sensitive AND value is not a supported container:
        #     CARRY the same scalar value into the cleansed result unchanged.
        #
        # GUID: SAFE-004 - Preserve supported container structure and ordering.
        # WHEN reconstructing a dictionary, list, or tuple:
        #     CREATE the same container kind at the same nesting position.
        #     PLACE each recursively cleansed entry or item in its original order.
        #     PRESERVE dictionary keys and associate each key with its cleansed value.
        #
        # GUID: SAFE-005 - Keep cleansing separate from the source value.
        # FOR EACH supported source container:
        #     READ entries or items without assigning into the source container.
        #     BUILD a distinct result container from recursively produced values.
        # IF a sensitive entry is reached:
        #     PLACE the substitute only in the result; leave the source value intact.
        # RETURN the completed result without mutating any source value or container.
        #
        # GUID: SAFE-003, SAFE-004, SAFE-005 - Preserve mixed-container integrity.
        # FOR EACH safe or sensitive value in a nested supported container:
        #     APPLY the sensitive-key decision independently at its original position.
        #     CARRY safe scalars unchanged and sensitive substitutes into the new result.
        #     RECONSTRUCT every enclosing container with its original kind and order.
        #     NEVER write any produced value back into the source container graph.
        #
        # GUID: SAFE-006 - Preserve scalar traversal boundaries.
        # ELSE value is unsupported or scalar, including every string:
        #     RETURN value unchanged; do not iterate it.
        # Treat every dictionary key only as the key input to matching; never traverse it.
        # IF sensitive-key matching rejects a non-regexable key with TypeError:
        #     RETURN its associated value unchanged and do not descend.
        try:
            if self.hidden_settings.search(key):
                cleansed = self.cleansed_substitute
            elif isinstance(value, dict):
                cleansed = {k: self.cleanse_setting(k, v) for k, v in value.items()}
            elif isinstance(value, list):
                cleansed = [self.cleanse_setting('', item) for item in value]
            elif isinstance(value, tuple):
                cleansed = tuple(self.cleanse_setting('', item) for item in value)
            else:
                cleansed = value
        except TypeError:
            # If the key isn't regex-able, just return as-is.
            cleansed = value

        if callable(cleansed):
            cleansed = CallableSettingWrapper(cleansed)

        return cleansed

    def get_safe_settings(self):
        """
        Return a dictionary of the settings module with values of sensitive
        settings replaced with stars (*********).
        """
        settings_dict = {}
        for k in dir(settings):
            if k.isupper():
                settings_dict[k] = self.cleanse_setting(k, getattr(settings, k))
        return settings_dict

    def get_safe_request_meta(self, request):
        """
        Return a dictionary of request.META with sensitive values redacted.
        """
        if not hasattr(request, 'META'):
            return {}
        return {k: self.cleanse_setting(k, v) for k, v in request.META.items()}

    def is_active(self, request):
        """
        This filter is to add safety in production environments (i.e. DEBUG
        is False). If DEBUG is True then your site is not safe anyway.
        This hook is provided as a convenience to easily activate or
        deactivate the filter on a per request basis.
        """
        return settings.DEBUG is False

    def get_cleansed_multivaluedict(self, request, multivaluedict):
        """
        Replace the keys in a MultiValueDict marked as sensitive with stars.
        This mitigates leaking sensitive POST parameters if something like
        request.POST['nonexistent_key'] throws an exception (#21098).
        """
        sensitive_post_parameters = getattr(request, 'sensitive_post_parameters', [])
        if self.is_active(request) and sensitive_post_parameters:
            multivaluedict = multivaluedict.copy()
            for param in sensitive_post_parameters:
                if param in multivaluedict:
                    multivaluedict[param] = self.cleansed_substitute
        return multivaluedict

    def get_post_parameters(self, request):
        """
        Replace the values of POST parameters marked as sensitive with
        stars (*********).
        """
        if request is None:
            return {}
        else:
            sensitive_post_parameters = getattr(request, 'sensitive_post_parameters', [])
            if self.is_active(request) and sensitive_post_parameters:
                cleansed = request.POST.copy()
                if sensitive_post_parameters == '__ALL__':
                    # Cleanse all parameters.
                    for k in cleansed:
                        cleansed[k] = self.cleansed_substitute
                    return cleansed
                else:
                    # Cleanse only the specified parameters.
                    for param in sensitive_post_parameters:
                        if param in cleansed:
                            cleansed[param] = self.cleansed_substitute
                    return cleansed
            else:
                return request.POST

    def cleanse_special_types(self, request, value):
        try:
            # If value is lazy or a complex object of another kind, this check
            # might raise an exception. isinstance checks that lazy
            # MultiValueDicts will have a return value.
            is_multivalue_dict = isinstance(value, MultiValueDict)
        except Exception as e:
            return '{!r} while evaluating {!r}'.format(e, value)

        if is_multivalue_dict:
            # Cleanse MultiValueDicts (request.POST is the one we usually care about)
            value = self.get_cleansed_multivaluedict(request, value)
        return value

    def get_traceback_frame_variables(self, request, tb_frame):
        """
        Replace the values of variables marked as sensitive with
        stars (*********).
        """
        # Loop through the frame's callers to see if the sensitive_variables
        # decorator was used.
        current_frame = tb_frame.f_back
        sensitive_variables = None
        while current_frame is not None:
            if (current_frame.f_code.co_name == 'sensitive_variables_wrapper' and
                    'sensitive_variables_wrapper' in current_frame.f_locals):
                # The sensitive_variables decorator was used, so we take note
                # of the sensitive variables' names.
                wrapper = current_frame.f_locals['sensitive_variables_wrapper']
                sensitive_variables = getattr(wrapper, 'sensitive_variables', None)
                break
            current_frame = current_frame.f_back

        cleansed = {}
        if self.is_active(request) and sensitive_variables:
            if sensitive_variables == '__ALL__':
                # Cleanse all variables
                for name in tb_frame.f_locals:
                    cleansed[name] = self.cleansed_substitute
            else:
                # Cleanse specified variables
                for name, value in tb_frame.f_locals.items():
                    if name in sensitive_variables:
                        value = self.cleansed_substitute
                    else:
                        value = self.cleanse_special_types(request, value)
                    cleansed[name] = value
        else:
            # Potentially cleanse the request and any MultiValueDicts if they
            # are one of the frame variables.
            for name, value in tb_frame.f_locals.items():
                cleansed[name] = self.cleanse_special_types(request, value)

        if (tb_frame.f_code.co_name == 'sensitive_variables_wrapper' and
                'sensitive_variables_wrapper' in tb_frame.f_locals):
            # For good measure, obfuscate the decorated function's arguments in
            # the sensitive_variables decorator's frame, in case the variables
            # associated with those arguments were meant to be obfuscated from
            # the decorated function's frame.
            cleansed['func_args'] = self.cleansed_substitute
            cleansed['func_kwargs'] = self.cleansed_substitute

        return cleansed.items()


class ExceptionReporter:
    """Organize and coordinate reporting on exceptions."""
    def __init__(self, request, exc_type, exc_value, tb, is_email=False):
        self.request = request
        self.filter = get_exception_reporter_filter(self.request)
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.tb = tb
        self.is_email = is_email

        self.template_info = getattr(self.exc_value, 'template_debug', None)
        self.template_does_not_exist = False
        self.postmortem = None

    def get_traceback_data(self):
        """Return a dictionary containing traceback information."""
        if self.exc_type and issubclass(self.exc_type, TemplateDoesNotExist):
            self.template_does_not_exist = True
            self.postmortem = self.exc_value.chain or [self.exc_value]

        frames = self.get_traceback_frames()
        for i, frame in enumerate(frames):
            if 'vars' in frame:
                frame_vars = []
                for k, v in frame['vars']:
                    v = pprint(v)
                    # Trim large blobs of data
                    if len(v) > 4096:
                        v = '%s… <trimmed %d bytes string>' % (v[0:4096], len(v))
                    frame_vars.append((k, v))
                frame['vars'] = frame_vars
            frames[i] = frame

        unicode_hint = ''
        if self.exc_type and issubclass(self.exc_type, UnicodeError):
            start = getattr(self.exc_value, 'start', None)
            end = getattr(self.exc_value, 'end', None)
            if start is not None and end is not None:
                unicode_str = self.exc_value.args[1]
                unicode_hint = force_str(
                    unicode_str[max(start - 5, 0):min(end + 5, len(unicode_str))],
                    'ascii', errors='replace'
                )
        from django import get_version

        if self.request is None:
            user_str = None
        else:
            try:
                user_str = str(self.request.user)
            except Exception:
                # request.user may raise OperationalError if the database is
                # unavailable, for example.
                user_str = '[unable to retrieve the current user]'

        c = {
            'is_email': self.is_email,
            'unicode_hint': unicode_hint,
            'frames': frames,
            'request': self.request,
            'request_meta': self.filter.get_safe_request_meta(self.request),
            'user_str': user_str,
            'filtered_POST_items': list(self.filter.get_post_parameters(self.request).items()),
            'settings': self.filter.get_safe_settings(),
            'sys_executable': sys.executable,
            'sys_version_info': '%d.%d.%d' % sys.version_info[0:3],
            'server_time': timezone.now(),
            'django_version_info': get_version(),
            'sys_path': sys.path,
            'template_info': self.template_info,
            'template_does_not_exist': self.template_does_not_exist,
            'postmortem': self.postmortem,
        }
        if self.request is not None:
            c['request_GET_items'] = self.request.GET.items()
            c['request_FILES_items'] = self.request.FILES.items()
            c['request_COOKIES_items'] = self.request.COOKIES.items()
        # Check whether exception info is available
        if self.exc_type:
            c['exception_type'] = self.exc_type.__name__
        if self.exc_value:
            c['exception_value'] = str(self.exc_value)
        if frames:
            c['lastframe'] = frames[-1]
        return c

    def get_traceback_html(self):
        """Return HTML version of debug 500 HTTP error page."""
        with Path(CURRENT_DIR, 'templates', 'technical_500.html').open(encoding='utf-8') as fh:
            t = DEBUG_ENGINE.from_string(fh.read())
        c = Context(self.get_traceback_data(), use_l10n=False)
        return t.render(c)

    def get_traceback_text(self):
        """Return plain text version of debug 500 HTTP error page."""
        with Path(CURRENT_DIR, 'templates', 'technical_500.txt').open(encoding='utf-8') as fh:
            t = DEBUG_ENGINE.from_string(fh.read())
        c = Context(self.get_traceback_data(), autoescape=False, use_l10n=False)
        return t.render(c)

    def _get_source(self, filename, loader, module_name):
        source = None
        if hasattr(loader, 'get_source'):
            try:
                source = loader.get_source(module_name)
            except ImportError:
                pass
            if source is not None:
                source = source.splitlines()
        if source is None:
            try:
                with open(filename, 'rb') as fp:
                    source = fp.read().splitlines()
            except OSError:
                pass
        return source

    def _get_lines_from_file(self, filename, lineno, context_lines, loader=None, module_name=None):
        """
        Return context_lines before and after lineno from file.
        Return (pre_context_lineno, pre_context, context_line, post_context).
        """
        source = self._get_source(filename, loader, module_name)
        if source is None:
            return None, [], None, []

        # If we just read the source from a file, or if the loader did not
        # apply tokenize.detect_encoding to decode the source into a
        # string, then we should do that ourselves.
        if isinstance(source[0], bytes):
            encoding = 'ascii'
            for line in source[:2]:
                # File coding may be specified. Match pattern from PEP-263
                # (https://www.python.org/dev/peps/pep-0263/)
                match = re.search(br'coding[:=]\s*([-\w.]+)', line)
                if match:
                    encoding = match.group(1).decode('ascii')
                    break
            source = [str(sline, encoding, 'replace') for sline in source]

        lower_bound = max(0, lineno - context_lines)
        upper_bound = lineno + context_lines

        try:
            pre_context = source[lower_bound:lineno]
            context_line = source[lineno]
            post_context = source[lineno + 1:upper_bound]
        except IndexError:
            return None, [], None, []
        return lower_bound, pre_context, context_line, post_context

    def get_traceback_frames(self):
        def explicit_or_implicit_cause(exc_value):
            explicit = getattr(exc_value, '__cause__', None)
            implicit = getattr(exc_value, '__context__', None)
            return explicit or implicit

        # Get the exception and all its causes
        exceptions = []
        exc_value = self.exc_value
        while exc_value:
            exceptions.append(exc_value)
            exc_value = explicit_or_implicit_cause(exc_value)
            if exc_value in exceptions:
                # Avoid infinite loop if there's a cyclic reference (#29393).
                break

        frames = []
        # No exceptions were supplied to ExceptionReporter
        if not exceptions:
            return frames

        # In case there's just one exception, take the traceback from self.tb
        exc_value = exceptions.pop()
        tb = self.tb if not exceptions else exc_value.__traceback__

        while tb is not None:
            # Support for __traceback_hide__ which is used by a few libraries
            # to hide internal frames.
            if tb.tb_frame.f_locals.get('__traceback_hide__'):
                tb = tb.tb_next
                continue
            filename = tb.tb_frame.f_code.co_filename
            function = tb.tb_frame.f_code.co_name
            lineno = tb.tb_lineno - 1
            loader = tb.tb_frame.f_globals.get('__loader__')
            module_name = tb.tb_frame.f_globals.get('__name__') or ''
            pre_context_lineno, pre_context, context_line, post_context = self._get_lines_from_file(
                filename, lineno, 7, loader, module_name,
            )
            if pre_context_lineno is None:
                pre_context_lineno = lineno
                pre_context = []
                context_line = '<source code not available>'
                post_context = []
            frames.append({
                'exc_cause': explicit_or_implicit_cause(exc_value),
                'exc_cause_explicit': getattr(exc_value, '__cause__', True),
                'tb': tb,
                'type': 'django' if module_name.startswith('django.') else 'user',
                'filename': filename,
                'function': function,
                'lineno': lineno + 1,
                'vars': self.filter.get_traceback_frame_variables(self.request, tb.tb_frame),
                'id': id(tb),
                'pre_context': pre_context,
                'context_line': context_line,
                'post_context': post_context,
                'pre_context_lineno': pre_context_lineno + 1,
            })

            # If the traceback for current exception is consumed, try the
            # other exception.
            if not tb.tb_next and exceptions:
                exc_value = exceptions.pop()
                tb = exc_value.__traceback__
            else:
                tb = tb.tb_next

        return frames


def technical_404_response(request, exception):
    """Create a technical 404 error response. `exception` is the Http404."""
    try:
        error_url = exception.args[0]['path']
    except (IndexError, TypeError, KeyError):
        error_url = request.path_info[1:]  # Trim leading slash

    try:
        tried = exception.args[0]['tried']
    except (IndexError, TypeError, KeyError):
        tried = []
    else:
        if (not tried or (                  # empty URLconf
            request.path == '/' and
            len(tried) == 1 and             # default URLconf
            len(tried[0]) == 1 and
            getattr(tried[0][0], 'app_name', '') == getattr(tried[0][0], 'namespace', '') == 'admin'
        )):
            return default_urlconf(request)

    urlconf = getattr(request, 'urlconf', settings.ROOT_URLCONF)
    if isinstance(urlconf, types.ModuleType):
        urlconf = urlconf.__name__

    caller = ''
    try:
        resolver_match = resolve(request.path)
    except Http404:
        pass
    else:
        obj = resolver_match.func

        if hasattr(obj, '__name__'):
            caller = obj.__name__
        elif hasattr(obj, '__class__') and hasattr(obj.__class__, '__name__'):
            caller = obj.__class__.__name__

        if hasattr(obj, '__module__'):
            module = obj.__module__
            caller = '%s.%s' % (module, caller)

    with Path(CURRENT_DIR, 'templates', 'technical_404.html').open(encoding='utf-8') as fh:
        t = DEBUG_ENGINE.from_string(fh.read())
    reporter_filter = get_default_exception_reporter_filter()
    c = Context({
        'urlconf': urlconf,
        'root_urlconf': settings.ROOT_URLCONF,
        'request_path': error_url,
        'urlpatterns': tried,
        'reason': str(exception),
        'request': request,
        'settings': reporter_filter.get_safe_settings(),
        'raising_view_name': caller,
    })
    return HttpResponseNotFound(t.render(c), content_type='text/html')


def default_urlconf(request):
    """Create an empty URLconf 404 error response."""
    with Path(CURRENT_DIR, 'templates', 'default_urlconf.html').open(encoding='utf-8') as fh:
        t = DEBUG_ENGINE.from_string(fh.read())
    c = Context({
        'version': get_docs_version(),
    })

    return HttpResponse(t.render(c), content_type='text/html')
