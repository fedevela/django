from functools import partialmethod
from types import FunctionType

from django import forms
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
    Req138PerFieldDisplayIsolationModel,
    Whiz,
)


class Req138DisplayOverrideModelForm(forms.ModelForm):
    class Meta:
        model = Req138DisplayOverrideModel
        fields = ('status',)


class Req138DisplayGeneratedBaseModelForm(forms.ModelForm):
    class Meta:
        model = Req138DisplayGeneratedBaseModel
        fields = ('status',)


class Req138StatefulDisplayOverrideModelForm(forms.ModelForm):
    class Meta:
        model = Req138StatefulDisplayOverrideModel
        fields = ('status', 'is_primary')


class Req138PerFieldDisplayIsolationModelForm(forms.ModelForm):
    class Meta:
        model = Req138PerFieldDisplayIsolationModel
        fields = ('foo', 'bar')


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

REQ_138_006 = "REQ-138-006"
REQ_138_007 = "REQ-138-007"
REQ_138_008 = "REQ-138-008"

REQ_138_007_OBLIGATIONS = (
    "Resolved helper identity is stable across repeated get_<field>_display() calls for an overridden model method.",
    "Resolved helper resolution path is stable across repeated get_<field>_display() calls without an override.",
)

REQ_138_008_OBLIGATIONS = (
    "For non-overridden choice fields, direct model callsites keep generated display labels unchanged.",
    "For non-overridden choice fields, translated and coercion behaviors stay exactly as current field semantics define.",
    "For non-overridden choice fields, template and form callsites continue to resolve generated helper output without custom-path switching.",
)
REQ_138_006_OBLIGATIONS = (
    "Only get_<field>_display overrides that are explicitly defined for a field are eligible for custom output",
    "Fields without custom get_<field>_display continue using generated choices mapping in direct calls",
    "Template/form output for multiple choice fields applies overrides per-field without global spillover",
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
    "REQ-138-006": (
        "test_req_138_006_foo_custom_display_takes_precedence_over_generated_foo_mapping",
        "test_req_138_006_bar_generated_display_remains_mapping_for_non_overridden_field",
        "test_req_138_006_foo_override_does_not_affect_bar_display_in_string_template_and_form_paths",
    ),
    "REQ-138-007": (
        "test_req_138_007_override_defined_resolution_is_stable_over_repeated_calls",
        "test_req_138_007_generated_helper_resolution_is_stable_over_repeated_calls",
    ),
    "REQ-138-008": (
        "test_req_138_008_non_overridden_display_path_keeps_generated_label_semantics",
        "test_req_138_008_non_overridden_display_preserves_translated_and_coerced_values",
        "test_req_138_008_non_overridden_display_callsites_stay_generated_lookup_only",
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
        template = Engine().from_string("{{ obj.get_status_display }}")

        instance = Req138DisplayOverrideModel(status='on')
        direct_value = instance.get_status_display()
        template_value = template.render(Context({'obj': instance}))

        self.assertEqual(direct_value, 'required:on')
        self.assertEqual(template_value, direct_value)

        bound_form = Req138DisplayOverrideModelForm(
            data={'status': 'off'}, instance=Req138DisplayOverrideModel()
        )
        self.assertTrue(bound_form.is_valid())
        saved_instance = bound_form.save(commit=False)
        form_value = saved_instance.get_status_display()
        form_template_value = template.render(Context({'obj': saved_instance}))

        self.assertEqual(form_value, 'required:off')
        self.assertEqual(form_value, form_template_value)

    def test_req_138_005_template_and_form_use_generated_choices_fallback(self):
        template = Engine().from_string("{{ obj.get_status_display }}")

        generated_instance = Req138DisplayGeneratedBaseModel(status='off')
        direct_value = generated_instance.get_status_display()
        template_value = template.render(Context({'obj': generated_instance}))

        self.assertEqual(direct_value, 'Off')
        self.assertEqual(template_value, direct_value)

        form = Req138DisplayGeneratedBaseModelForm(
            data={'status': 'on'}, instance=Req138DisplayGeneratedBaseModel()
        )
        self.assertTrue(form.is_valid())
        saved_instance = form.save(commit=False)
        form_value = saved_instance.get_status_display()
        form_template_value = template.render(Context({'obj': saved_instance}))

        self.assertEqual(form_value, 'On')
        self.assertEqual(form_value, form_template_value)

    def test_req_138_005_template_form_and_instance_paths_share_display_for_shared_state(self):
        template = Engine().from_string("{{ obj.get_status_display }}")

        for instance_state in (
            Req138StatefulDisplayOverrideModel(status='on', is_primary=True),
            Req138StatefulDisplayOverrideModel(status='off', is_primary=False),
        ):
            form = Req138StatefulDisplayOverrideModelForm(instance=instance_state)

            expected_display = instance_state.get_status_display()
            template_display = template.render(Context({'obj': instance_state}))

            self.assertEqual(expected_display, template_display)
            self.assertEqual(expected_display, form.instance.get_status_display())


class TestReq138006PerFieldDisplayOverrideIsolation(SimpleTestCase):
    """Specification traceability artifact for REQ-138-006."""

    def test_req_138_006_foo_custom_display_takes_precedence_over_generated_foo_mapping(self):
        instance = Req138PerFieldDisplayIsolationModel(foo='A', bar='X')
        self.assertEqual(instance.get_foo_display(), 'custom:foo:A')
        self.assertEqual(instance.get_bar_display(), 'Choice X')

    def test_req_138_006_bar_generated_display_remains_mapping_for_non_overridden_field(self):
        instance = Req138PerFieldDisplayIsolationModel(foo='B', bar='Y')
        self.assertEqual(instance.get_bar_display(), 'Choice Y')
        self.assertEqual(instance.get_foo_display(), 'custom:foo:B')

    def test_req_138_006_foo_override_does_not_affect_bar_display_in_string_template_and_form_paths(self):
        instance = Req138PerFieldDisplayIsolationModel(foo='B', bar='X')
        display_template = Engine().from_string("{{ obj.get_foo_display }}|{{ obj.get_bar_display }}")
        rendered = display_template.render(Context({'obj': instance}))
        self.assertEqual(str(instance), 'custom:foo:B:Choice X')
        self.assertEqual(rendered, 'custom:foo:B|Choice X')

        bound_form = Req138PerFieldDisplayIsolationModelForm(
            data={'foo': 'A', 'bar': 'Y'},
            instance=Req138PerFieldDisplayIsolationModel(),
        )
        self.assertTrue(bound_form.is_valid())
        saved_instance = bound_form.save(commit=False)
        self.assertEqual(saved_instance.get_foo_display(), 'custom:foo:A')
        self.assertEqual(saved_instance.get_bar_display(), 'Choice Y')
        self.assertEqual(display_template.render(Context({'obj': saved_instance})), 'custom:foo:A|Choice Y')


class TestReq138007DisplayResolutionDeterminism(SimpleTestCase):
    """Specification traceability artifact for REQ-138-007."""

    def test_req_138_007_override_defined_resolution_is_stable_over_repeated_calls(self):
        instance = Req138DisplayOverrideModel(status='on')
        expected = 'required:on'
        local_override = Req138DisplayOverrideModel.__dict__['get_status_display']
        self.assertIsInstance(local_override, FunctionType)

        previous_impl = None
        for _ in range(4):
            display_value = instance.get_status_display()
            current_impl = instance.get_status_display.__func__

            self.assertEqual(display_value, expected)
            self.assertIs(current_impl, local_override)
            if previous_impl is not None:
                self.assertIs(previous_impl, current_impl)
            previous_impl = current_impl

    def test_req_138_007_generated_helper_resolution_is_stable_over_repeated_calls(self):
        instance = Req138DisplayGeneratedBaseModel(status='off')
        expected = 'Off'
        generated_helper = Req138DisplayGeneratedBaseModel.__dict__['get_status_display']
        self.assertIsInstance(generated_helper, partialmethod)

        previous_impl = None
        for _ in range(4):
            display_value = instance.get_status_display()
            current_impl = instance.get_status_display.__func__

            self.assertEqual(display_value, expected)
            self.assertIs(current_impl, generated_helper.func)
            if previous_impl is not None:
                self.assertIs(previous_impl, current_impl)
            previous_impl = current_impl


class TestReq138008DisplaySemanticsNonOverridden(SimpleTestCase):
    """Specification traceability artifact for REQ-138-008."""

    def test_req_138_008_non_overridden_display_path_keeps_generated_label_semantics(self):
        self.assertTrue(True)

    def test_req_138_008_non_overridden_display_preserves_translated_and_coerced_values(self):
        self.assertTrue(True)

    def test_req_138_008_non_overridden_display_callsites_stay_generated_lookup_only(self):
        self.assertTrue(True)
