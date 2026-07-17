from inspect import signature

from django.test import SimpleTestCase
from django.template.defaultfilters import json_script

from ..utils import setup


class JsonScriptTests(SimpleTestCase):
    @setup({"jsonscript-008": '{{ value|json_script:"test_id" }}'})
    def test_jsonscript_008_existing_filter_interface_render_preserves_output(self):
        """JSONSCRIPT-008: Rendering via the existing interface preserves output."""
        output = self.engine.render_to_string(
            "jsonscript-008", {"value": {"key": "</script>&"}}
        )
        self.assertEqual(
            output,
            '<script id="test_id" type="application/json">'
            '{"key": "\\u003C/script\\u003E\\u0026"}</script>',
        )

    def test_jsonscript_008_python_encoder_selection_does_not_extend_filter_interface(self):
        """JSONSCRIPT-008: Python encoder selection stays outside the filter API."""
        parameters = signature(json_script).parameters
        self.assertEqual(tuple(parameters), ("value", "element_id"))
        self.assertIsNone(parameters["element_id"].default)

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
