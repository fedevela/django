import enum

from django.db import models
from django.db.migrations.writer import MigrationWriter
from django.test import SimpleTestCase


class Outer:
    class Inner(models.CharField):
        pass


class Thing:
    class State(enum.Enum):
        ON = "on"
        OFF = "off"


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

    def test_m154_004_unresolvable_nested_reference_raises_non_serializable_local_scope_error(self):
        class LocalModel:
            class State(enum.Enum):
                ON = "on"
                OFF = "off"

        with self.assertRaisesMessage(
            ValueError, "Could not find class State in %s." % __name__
        ):
            MigrationWriter.serialize(EnumField(enum=LocalModel.State))
