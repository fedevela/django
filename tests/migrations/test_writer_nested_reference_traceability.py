import enum

import re

from django.db import migrations, models
from django.db.migrations.writer import MigrationWriter
from django.test import SimpleTestCase


class Outer:
    class Inner(models.CharField):
        pass


class Thing:
    class State(enum.Enum):
        ON = "on"
        OFF = "off"


class TopLevelField(models.Field):
    pass


def top_level_callable():
    return "top-level"


class EnumField(models.Field):
    def __init__(self, *, enum, **kwargs):
        self.enum = enum
        super().__init__(**kwargs)

    def deconstruct(self):
        return (
            "%s.%s" % (self.__class__.__module__, self.__class__.__qualname__),
            [],
            {"enum": self.enum},
        )


REQUIREMENT_TO_VERIFICATION = {
    "M154-001": [
        "test_m154_001_deconstruct_nested_field_subclass_emits_full_outer_inner_path"
    ],
    "M154-002": [
        "test_m154_002_deconstruct_model_local_nested_enum_option_emits_model_qualified_path"
    ],
    "M154-003": [
        "test_m154_003_top_level_deconstructible_path_remains_non_nested_format_after_nested_fixes"
    ],
    "M154-005": [
        "test_m154_005_nested_reference_shape_is_deterministic_across_reordered_and_repeated_fields"
    ],
    "M154-004": [
        "test_m154_004_unresolvable_nested_reference_raises_non_serializable_local_scope_error"
    ],
}


class NestedReferenceTraceabilityTests(SimpleTestCase):
    """Contract-focused verification placeholders for nested deconstruction paths."""

    def test_m154_001_deconstruct_nested_field_subclass_emits_full_outer_inner_path(self):
        field = Outer.Inner(max_length=20)
        string, imports = MigrationWriter.serialize(field)
        self.assertEqual(
            string,
            "%s.Outer.Inner(max_length=20)" % __name__,
        )
        self.assertIn("import %s" % __name__, imports)

    def test_m154_002_deconstruct_model_local_nested_enum_option_emits_model_qualified_path(self):
        field = EnumField(enum=Thing.State)
        string, imports = MigrationWriter.serialize(field)
        self.assertEqual(
            string,
            "%s.EnumField(enum=%s.Thing.State)" % (__name__, __name__),
        )
        self.assertIn("import %s" % __name__, imports)

    def test_m154_003_top_level_deconstructible_path_remains_non_nested_format_after_nested_fixes(self):
        field = TopLevelField()
        field_string, field_imports = MigrationWriter.serialize(field)
        self.assertEqual(field_string, "%s.TopLevelField()" % __name__)
        self.assertEqual(field_imports, {"import %s" % __name__})

        function_string, function_imports = MigrationWriter.serialize(top_level_callable)
        self.assertEqual(function_string, "%s.top_level_callable" % __name__)
        self.assertEqual(function_imports, {"import %s" % __name__})

        enum_string, enum_imports = MigrationWriter.serialize(Thing.State)
        self.assertEqual(enum_string, "%s.Thing.State" % __name__)
        self.assertEqual(enum_imports, {"import %s" % __name__})

    def test_m154_004_unresolvable_nested_reference_raises_non_serializable_local_scope_error(self):
        class LocalModel:
            class State(enum.Enum):
                ON = "on"
                OFF = "off"

        with self.assertRaisesMessage(
            ValueError, "Could not find class State in %s." % __name__
        ):
            MigrationWriter.serialize(EnumField(enum=LocalModel.State))

    def test_m154_005_nested_reference_shape_is_deterministic_across_reordered_and_repeated_fields(self):
        fields_a = [
            ("first_state", EnumField(enum=Thing.State)),
            ("second_state", EnumField(enum=Thing.State)),
        ]
        fields_b = [
            ("second_state", EnumField(enum=Thing.State)),
            ("first_state", EnumField(enum=Thing.State)),
        ]

        operation_a = migrations.CreateModel(
            "Model", fields=fields_a, options={}, bases=(models.Model,)
        )
        operation_b = migrations.CreateModel(
            "Model", fields=fields_b, options={}, bases=(models.Model,)
        )

        string_a, _ = MigrationWriter.serialize(operation_a)
        string_b, _ = MigrationWriter.serialize(operation_b)

        expected_path = "%s.Thing.State" % __name__
        self.assertEqual(string_a.count(expected_path), 2)
        self.assertEqual(string_b.count(expected_path), 2)
        self.assertEqual(
            set(re.findall(r"%s\\.Thing\\.State" % re.escape(__name__), string_a)),
            set(re.findall(r"%s\\.Thing\\.State" % re.escape(__name__), string_b)),
        )
