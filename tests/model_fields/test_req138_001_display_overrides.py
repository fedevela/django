from django.test import SimpleTestCase
from django.template import Context, Engine

from .models import (
    Req138DisplayOverrideModel,
    Req138StatefulDisplayOverrideModel,
    Whiz,
)


REQ_138_001 = "REQ-138-001"
REQ_138_001_OBLIGATIONS = (
    "Get model-defined get_<field>_display override precedence in direct model call",
    "Get model-defined get_<field>_display override precedence through __str__ path",
    "Get model-defined get_<field>_display override precedence in template expression path",
    "Repeat direct and template call paths against same state-dependent override result",
)

REQ_138_002 = "REQ-138-002"
REQ_138_002_OBLIGATIONS = (
    "For choice fields without custom get_<field>_display, get_<field>_display resolves mapped labels from choices",
    "For multiple instances, generated get_<field>_display remains value-specific and instance-independent",
)

REQ_ID_TO_VERIFICATION = {
    "REQ-138-001": (
        "test_req_138_001_direct_call_uses_model_defined_display_override",
        "test_req_138_001_str_uses_model_defined_get_field_display_override",
        "test_req_138_001_template_expression_uses_model_defined_get_field_display_override",
        "test_req_138_001_stateful_override_is_consistent_across_direct_and_template_calls",
    ),
    "REQ-138-002": (
        "test_req_138_002_generated_display_uses_choices_map_for_non_overridden_field_value_1",
        "test_req_138_002_generated_display_resolves_label_for_multiple_instances",
    ),
}


class TestReq138001DisplayOverridePrecedence(SimpleTestCase):
    """Specification traceability artifact for REQ-138-001."""

    def test_req_138_001_direct_call_uses_model_defined_display_override(self):
        instance = Req138DisplayOverrideModel(status='on')
        self.assertEqual(instance.get_status_display(), 'required:on')

    def test_req_138_001_str_uses_model_defined_get_field_display_override(self):
        instance = Req138DisplayOverrideModel(status='off')
        self.assertEqual(str(instance), 'required:off')

    def test_req_138_001_template_expression_uses_model_defined_get_field_display_override(self):
        instance = Req138DisplayOverrideModel(status='on')
        template = Engine().from_string("{{ obj.get_status_display }}")
        rendered = template.render(Context({'obj': instance}))
        self.assertEqual(rendered, 'required:on')

    def test_req_138_001_stateful_override_is_consistent_across_direct_and_template_calls(self):
        instance = Req138StatefulDisplayOverrideModel(status='on', is_primary=True)
        template = Engine().from_string("{{ obj.get_status_display }}")

        direct_value = instance.get_status_display()
        template_value = template.render(Context({'obj': instance}))
        self.assertEqual(direct_value, template_value)
        self.assertEqual(direct_value, 'primary:on')

        instance.is_primary = False
        direct_value = instance.get_status_display()
        template_value = template.render(Context({'obj': instance}))
        self.assertEqual(direct_value, template_value)
        self.assertEqual(direct_value, 'secondary:on')


class TestReq138002DisplayFallbackToChoices(SimpleTestCase):
    """Specification traceability artifact for REQ-138-002."""

    def test_req_138_002_generated_display_uses_choices_map_for_non_overridden_field_value_1(self):
        instance = Whiz(c=1)
        self.assertEqual(instance.get_c_display(), "First")

    def test_req_138_002_generated_display_resolves_label_for_multiple_instances(self):
        on = Whiz(c=1)
        off = Whiz(c=0)
        self.assertEqual(on.get_c_display(), "First")
        self.assertEqual(off.get_c_display(), "Other")
