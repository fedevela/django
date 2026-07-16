from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from django import template
from django.apps import apps
from django.urls import get_script_prefix
from django.utils.encoding import iri_to_uri
from django.utils.html import conditional_escape

register = template.Library()


def _url_with_script_prefix(url):
    """Add the current script prefix to an application-relative URL."""
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        return url

    script_prefix = get_script_prefix()
    if not script_prefix or script_prefix == '/':
        return url

    script_path = script_prefix.rstrip('/')
    if parsed.path == script_path or parsed.path.startswith(script_path + '/'):
        return url

    path = '%s/%s' % (script_path, parsed.path.lstrip('/'))
    return urlunsplit((parsed.scheme, parsed.netloc, path,
                       parsed.query, parsed.fragment))


class PrefixNode(template.Node):

    def __repr__(self):
        return "<PrefixNode for %r>" % self.name

    def __init__(self, varname=None, name=None):
        if name is None:
            raise template.TemplateSyntaxError(
                "Prefix nodes must be given a name to return.")
        self.varname = varname
        self.name = name

    @classmethod
    def handle_token(cls, parser, token, name):
        """
        Class method to parse prefix node and return a Node.
        """
        # token.split_contents() isn't useful here because tags using this method don't accept variable as arguments
        tokens = token.contents.split()
        if len(tokens) > 1 and tokens[1] != 'as':
            raise template.TemplateSyntaxError(
                "First argument in '%s' must be 'as'" % tokens[0])
        if len(tokens) > 1:
            varname = tokens[2]
        else:
            varname = None
        return cls(varname, name)

    @classmethod
    def handle_simple(cls, name):
        try:
            from django.conf import settings
        except ImportError:
            prefix = ''
        else:
            prefix = iri_to_uri(getattr(settings, name, ''))
        return _url_with_script_prefix(prefix)

    def render(self, context):
        prefix = self.handle_simple(self.name)
        if self.varname is None:
            return prefix
        context[self.varname] = prefix
        return ''


@register.tag
def get_static_prefix(parser, token):
    """
    Populate a template variable with the static prefix,
    ``settings.STATIC_URL``.

    Usage::

        {% get_static_prefix [as varname] %}

    Examples::

        {% get_static_prefix %}
        {% get_static_prefix as static_prefix %}
    """
    return PrefixNode.handle_token(parser, token, "STATIC_URL")


@register.tag
def get_media_prefix(parser, token):
    """
    Populate a template variable with the media prefix,
    ``settings.MEDIA_URL``.

    Usage::

        {% get_media_prefix [as varname] %}

    Examples::

        {% get_media_prefix %}
        {% get_media_prefix as media_prefix %}
    """
    return PrefixNode.handle_token(parser, token, "MEDIA_URL")


class StaticNode(template.Node):
    def __init__(self, varname=None, path=None):
        if path is None:
            raise template.TemplateSyntaxError(
                "Static template nodes must be given a path to return.")
        self.path = path
        self.varname = varname

    def url(self, context):
        path = self.path.resolve(context)
        return self.handle_simple(path)

    def render(self, context):
        # Default static tag output pseudocode
        # (GUID: SCRIPTURL-003, GUID: SCRIPTURL-004):
        #
        # PROCEDURE render_default_static_tag(context, requested_path,
        #                                     optional_assignment_name):
        #     resolved_path <- resolve requested_path from context
        #     asset_url <- build the static asset URL once for resolved_path
        #                  using the active request's script prefix
        #     IF the active script prefix is non-empty and non-root AND the
        #        configured static base is application-relative:
        #         REQUIRE asset_url contains it exactly once, before the
        #                 configured static path
        #     ELSE IF the active script prefix is absent, empty, or root:
        #         REQUIRE asset_url equals the existing unprefixed output
        #     escaped_url <- conditionally escape asset_url according to the
        #                    current context's existing autoescape behavior
        #     IF optional_assignment_name is absent:
        #         RETURN escaped_url for direct rendering
        #     context[optional_assignment_name] <- escaped_url
        #     RETURN an empty rendering, so assignment stores exactly the URL
        #            that direct rendering would return for the same inputs
        #     ON path resolution, URL construction, or escaping failure:
        #         propagate the existing error and do not assign a partial URL
        url = self.url(context)
        if context.autoescape:
            url = conditional_escape(url)
        if self.varname is None:
            return url
        context[self.varname] = url
        return ''

    @classmethod
    def handle_simple(cls, path):
        if apps.is_installed('django.contrib.staticfiles'):
            from django.contrib.staticfiles.storage import staticfiles_storage
            url = staticfiles_storage.url(path)
        else:
            url = urljoin(PrefixNode.handle_simple("STATIC_URL"), quote(path))
        return _url_with_script_prefix(url)

    @classmethod
    def handle_token(cls, parser, token):
        """
        Class method to parse prefix node and return a Node.
        """
        bits = token.split_contents()

        if len(bits) < 2:
            raise template.TemplateSyntaxError(
                "'%s' takes at least one argument (path to file)" % bits[0])

        path = parser.compile_filter(bits[1])

        if len(bits) >= 2 and bits[-2] == 'as':
            varname = bits[3]
        else:
            varname = None

        return cls(varname, path)


@register.tag('static')
def do_static(parser, token):
    """
    Join the given path with the STATIC_URL setting.

    Usage::

        {% static path [as varname] %}

    Examples::

        {% static "myapp/css/base.css" %}
        {% static variable_with_path %}
        {% static "myapp/css/base.css" as admin_base_css %}
        {% static variable_with_path as varname %}
    """
    return StaticNode.handle_token(parser, token)


def static(path):
    """
    Given a relative path to a static asset, return the absolute path to the
    asset.
    """
    return StaticNode.handle_simple(path)
