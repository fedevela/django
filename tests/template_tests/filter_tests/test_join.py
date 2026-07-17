from django.template.defaultfilters import join
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class JoinTests(SimpleTestCase):
    @setup({"join01": '{{ a|join:", " }}'})
    def test_join01(self):
        output = self.engine.render_to_string("join01", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha, beta &amp; me")

    @setup({"join02": '{% autoescape off %}{{ a|join:", " }}{% endautoescape %}'})
    def test_join02(self):
        output = self.engine.render_to_string("join02", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha, beta & me")

    @setup({"join03": '{{ a|join:" &amp; " }}'})
    def test_join03(self):
        output = self.engine.render_to_string("join03", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join04": '{% autoescape off %}{{ a|join:" &amp; " }}{% endautoescape %}'})
    def test_join04(self):
        output = self.engine.render_to_string("join04", {"a": ["alpha", "beta & me"]})
        self.assertEqual(output, "alpha &amp; beta & me")

    # Joining with unsafe joiners doesn't result in unsafe strings.
    @setup({"join05": "{{ a|join:var }}"})
    def test_join05(self):
        output = self.engine.render_to_string(
            "join05", {"a": ["alpha", "beta & me"], "var": " & "}
        )
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join06": "{{ a|join:var }}"})
    def test_join06(self):
        output = self.engine.render_to_string(
            "join06", {"a": ["alpha", "beta & me"], "var": mark_safe(" & ")}
        )
        self.assertEqual(output, "alpha & beta &amp; me")

    @setup({"join07": "{{ a|join:var|lower }}"})
    def test_join07(self):
        output = self.engine.render_to_string(
            "join07", {"a": ["Alpha", "Beta & me"], "var": " & "}
        )
        self.assertEqual(output, "alpha &amp; beta &amp; me")

    @setup({"join08": "{{ a|join:var|lower }}"})
    def test_join08(self):
        output = self.engine.render_to_string(
            "join08", {"a": ["Alpha", "Beta & me"], "var": mark_safe(" & ")}
        )
        self.assertEqual(output, "alpha & beta &amp; me")


class JoinContractTraceabilityTests(SimpleTestCase):
    @setup(
        {
            "join_001": (
                "{% autoescape off %}{{ values|join:separator }}{% endautoescape %}"
            )
        }
    )
    def test_join_001_autoescape_disabled_context_separator_returns_direct_join(self):
        """JOIN-001: Preserve items and a context separator without escaping."""
        values = ["<first>", "second & last"]
        separator = " <&> "
        output = self.engine.render_to_string(
            "join_001", {"values": values, "separator": separator}
        )
        self.assertEqual(output, separator.join(values))

    @setup({"join_002": "{{ values|join:separator }}"})
    def test_join_002_autoescape_enabled_escapes_items_and_separator(self):
        """JOIN-002: Preserve HTML-safe escaping for items and the separator."""
        output = self.engine.render_to_string(
            "join_002",
            {"values": ["<first>", "second & last"], "separator": " <&> "},
        )
        self.assertEqual(
            output, "&lt;first&gt; &lt;&amp;&gt; second &amp; last"
        )

    @setup(
        {
            "literal": (
                '{% autoescape off %}{{ values|join:"<&>" }}{% endautoescape %}'
            ),
            "context": (
                "{% autoescape off %}{{ values|join:separator }}{% endautoescape %}"
            ),
        }
    )
    def test_join_003_autoescape_disabled_literal_and_context_separators_match(self):
        """JOIN-003: Apply disabled autoescape consistently to both separator forms."""
        context = {"values": ["<first>", "second & last"], "separator": "<&>"}
        literal = self.engine.render_to_string("literal", context)
        contextual = self.engine.render_to_string("context", context)
        self.assertEqual(literal, contextual)
        self.assertEqual(literal, "<first><&>second & last")

    @setup(
        {
            "literal": '{{ values|join:"<&>" }}',
            "context": "{{ values|join:separator }}",
        }
    )
    def test_join_003_autoescape_enabled_literal_and_context_separators_match(self):
        """JOIN-003: Apply enabled autoescape consistently to both separator forms."""
        context = {
            "values": ["<first>", "second & last"],
            "separator": mark_safe("<&>"),
        }
        literal = self.engine.render_to_string("literal", context)
        contextual = self.engine.render_to_string("context", context)
        self.assertEqual(literal, contextual)
        self.assertEqual(literal, "&lt;first&gt;<&>second &amp; last")

    @setup(
        {
            "join_004": (
                "{% autoescape off %}{{ values|join:separator }}{% endautoescape %}"
            )
        }
    )
    def test_join_004_autoescape_disabled_preserves_order_contents_and_semantics(self):
        """JOIN-004: Preserve valid joining behavior with autoescape disabled."""
        values = ("third >", "<first>", "second &")
        separator = " :: "
        output = self.engine.render_to_string(
            "join_004", {"values": values, "separator": separator}
        )
        self.assertEqual(output, separator.join(values))

    @setup({"join_004": "{{ values|join:separator }}"})
    def test_join_004_autoescape_enabled_preserves_order_contents_and_semantics(self):
        """JOIN-004: Preserve valid joining behavior with autoescape enabled."""
        output = self.engine.render_to_string(
            "join_004",
            {
                "values": ("third >", "<first>", "second &"),
                "separator": " :: ",
            },
        )
        self.assertEqual(output, "third &gt; :: &lt;first&gt; :: second &amp;")

    def test_join_005_autoescape_disabled_noniterable_preserves_fallback(self):
        """JOIN-005: Preserve the noniterable fallback with autoescape disabled."""
        value = object()
        self.assertIs(join(value, "<&>", autoescape=False), value)

    def test_join_005_autoescape_enabled_noniterable_preserves_fallback(self):
        """JOIN-005: Preserve the noniterable fallback with autoescape enabled."""
        value = object()
        self.assertIs(join(value, "<&>", autoescape=True), value)


class FunctionTests(SimpleTestCase):
    def test_list(self):
        self.assertEqual(join([0, 1, 2], "glue"), "0glue1glue2")

    def test_autoescape(self):
        self.assertEqual(
            join(["<a>", "<img>", "</a>"], "<br>"),
            "&lt;a&gt;&lt;br&gt;&lt;img&gt;&lt;br&gt;&lt;/a&gt;",
        )

    def test_autoescape_off(self):
        self.assertEqual(
            join(["<a>", "<img>", "</a>"], "<br>", autoescape=False),
            "<a><br><img><br></a>",
        )

    def test_noniterable_arg(self):
        obj = object()
        self.assertEqual(join(obj, "<br>"), obj)

    def test_noniterable_arg_autoescape_off(self):
        obj = object()
        self.assertEqual(join(obj, "<br>", autoescape=False), obj)
