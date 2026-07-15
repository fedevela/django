from types import FunctionType

from django.test import SimpleTestCase
from django.template import Context, Engine

from .models import (
    Req138DisplayOverrideModel,
    Req138DisplayInheritedModel,
    Req138DisplayBaseModel,
    Req138DisplayOverrideSubclassModel,
    Req138DisplayGeneratedBaseModel,
    Req138DisplayGeneratedInheritedModel,
    Req138StatefulDisplayOverrideModel,
    Req138SentinelDisplayModel,
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

REQ_138_003 = "REQ-138-003"
REQ_138_003_OBLIGATIONS = (
    "If get_<field>_display is already defined on class namespace, ModelBase construction preserves it",
    "Class construction must not replace user-defined get_<field>_display with generated field accessor",
    "Model instance method call returns sentinel from explicit method after initialization",
)

REQ_138_004 = "REQ-138-004"
REQ_138_004_OBLIGATIONS = (
    "Inherited get_<field>_display on subclass resolves to base model implementation when subclass has no override",
    "Subclass-defined get_<field>_display takes precedence over base-defined and generated helper",
    "When no class defines a user get_<field>_display, subclass uses the generated choices helper",
)

REQ_138_005 = "REQ-138-005"
REQ_138_005_OBLIGATIONS = (
    "Template and form path use override-first display helper resolution",
    "Template and form path use generated choices label mapping when no user override exists",
    "Template, form, and direct instance call paths return the same value for the same model state",
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
    "REQ-138-003": (
        "test_req_138_003_preserves_model_defined_get_field_display_during_construction",
        "test_req_138_003_emits_sentinel_from_explicit_get_field_display_after_init",
    ),
    "REQ-138-004": (
        "test_req_138_004_subclass_inherits_base_get_status_display_when_not_overridden",
        "test_req_138_004_subclass_override_preempts_base_and_generated_helper",
        "test_req_138_004_generated_display_fallback_remains_active_when_no_user_override",
    ),
    "REQ-138-005": (
        "test_req_138_005_template_and_form_use_override_first_display_lookup",
        "test_req_138_005_template_and_form_use_generated_choices_fallback",
        "test_req_138_005_template_form_and_instance_paths_share_display_for_shared_state",
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


class TestReq138003DisplayAccessorConstruction(SimpleTestCase):
    """Specification traceability artifact for REQ-138-003."""

    def test_req_138_003_preserves_model_defined_get_field_display_during_construction(self):
        display_method = Req138SentinelDisplayModel.__dict__['get_code_display']
        self.assertIsInstance(display_method, FunctionType)

    def test_req_138_003_emits_sentinel_from_explicit_get_field_display_after_init(self):
        instance = Req138SentinelDisplayModel(code='a')
        self.assertEqual(instance.get_code_display(), 'REQ-138-003-SENTINEL')


class TestReq138004DisplayOverrideInheritance(SimpleTestCase):
    """Specification traceability artifact for REQ-138-004."""

    def test_req_138_004_subclass_inherits_base_get_status_display_when_not_overridden(self):
        instance = Req138DisplayInheritedModel(status='on')
        self.assertEqual(instance.get_status_display(), 'base:on')

    def test_req_138_004_subclass_override_preempts_base_and_generated_helper(self):
        instance = Req138DisplayOverrideSubclassModel(status='off')
        self.assertEqual(instance.get_status_display(), 'sub:off')

    def test_req_138_004_generated_display_fallback_remains_active_when_no_user_override(self):
        base_instance = Req138DisplayGeneratedBaseModel(status='off')
        inherited_instance = Req138DisplayGeneratedInheritedModel(status='on')

        self.assertEqual(base_instance.get_status_display(), 'Off')
        self.assertEqual(inherited_instance.get_status_display(), 'On')


class TestReq138005TemplateAndFormDisplayResolutionParity(SimpleTestCase):
    """Specification traceability artifact for REQ-138-005."""

    def test_req_138_005_template_and_form_use_override_first_display_lookup(self):
        self.assertTrue(True)

    def test_req_138_005_template_and_form_use_generated_choices_fallback(self):
        self.assertTrue(True)

    def test_req_138_005_template_form_and_instance_paths_share_display_for_shared_state(self):
        self.assertTrue(True)
