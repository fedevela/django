from urllib.parse import quote, urljoin

from django import template
from django.apps import apps
from django.utils.encoding import iri_to_uri
from django.utils.html import conditional_escape

register = template.Library()


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
        # Request-scoped base resolution pseudocode
        # (GUID: SCRIPTURL-002, SCRIPTURL-008, SCRIPTURL-009, SCRIPTURL-010,
        # GUID: SCRIPTURL-011):
        #
        # PROCEDURE resolve_asset_base(setting_name):
        #     configured_base <- read setting_name using the existing empty
        #                        fallback and encode it as an IRI-safe URL
        #     IF configured_base has a scheme or network location:
        #         RETURN configured_base unchanged
        #     active_prefix <- read the current request's script prefix now;
        #                      do not cache it or write it back to settings
        #     IF active_prefix is absent, empty, or the root prefix:
        #         RETURN configured_base unchanged
        #     IF configured_base already starts with active_prefix on a path
        #        segment boundary:
        #         RETURN configured_base unchanged
        #     resolved_base <- active_prefix joined before configured_base,
        #                      preserving its path, query, and fragment
        #     HAND OFF resolved_base to static or media path composition;
        #              append the requested path beneath the complete base
        #              without altering either component
        #     RETURN resolved_base
        #     ON malformed input or failed URL conversion:
        #         propagate the existing error; retain no request state
        try:
            from django.conf import settings
        except ImportError:
            prefix = ''
        else:
            prefix = iri_to_uri(getattr(settings, name, ''))
        return prefix

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
        url = self.url(context)
        if context.autoescape:
            url = conditional_escape(url)
        if self.varname is None:
            return url
        context[self.varname] = url
        return ''

    @classmethod
    def handle_simple(cls, path):
        # Static asset composition pseudocode
        # (GUID: SCRIPTURL-001):
        #
        # PROCEDURE build_static_asset_url(requested_path):
        #     candidate_base <- resolve STATIC_URL through the request-scoped
        #                       base procedure above, including when the active
        #                       storage supplies the configured static base
        #     subordinate_path <- quote requested_path for URL use without
        #                         discarding candidate_base
        #     output <- join subordinate_path beneath candidate_base
        #     ASSERT output contains any usable active prefix exactly once,
        #            followed by the complete configured base and asset path
        #     RETURN output
        #     ON storage or quoting failure:
        #         propagate the existing error without returning a partial URL
        if apps.is_installed('django.contrib.staticfiles'):
            from django.contrib.staticfiles.storage import staticfiles_storage
            return staticfiles_storage.url(path)
        else:
            return urljoin(PrefixNode.handle_simple("STATIC_URL"), quote(path))

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
