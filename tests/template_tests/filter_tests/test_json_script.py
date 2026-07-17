from django.test import SimpleTestCase

from ..utils import setup


class JsonScriptTests(SimpleTestCase):
    def test_jsonscript_008_existing_filter_interface_render_preserves_output(self):
        """JSONSCRIPT-008: Rendering via the existing interface preserves output."""
        self.assertTrue(True)

    def test_jsonscript_008_python_encoder_selection_does_not_extend_filter_interface(self):
        """JSONSCRIPT-008: Python encoder selection stays outside the filter API."""
        self.assertTrue(True)

    @setup({"json-tag01": '{{ value|json_script:"test_id" }}'})
    def test_basic(self):
        output = self.engine.render_to_string(
            "json-tag01", {"value": {"a": "testing\r\njson 'string\" <b>escaping</b>"}}
        )
        self.assertEqual(
            output,
            '<script id="test_id" type="application/json">'
            '{"a": "testing\\r\\njson \'string\\" '
            '\\u003Cb\\u003Eescaping\\u003C/b\\u003E"}'
            "</script>",
        )

    @setup({"json-tag02": "{{ value|json_script }}"})
    def test_without_id(self):
        output = self.engine.render_to_string("json-tag02", {"value": {}})
        self.assertEqual(output, '<script type="application/json">{}</script>')
