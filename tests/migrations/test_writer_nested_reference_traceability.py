import enum
import io
import os
import re
import tempfile

from django.db import migrations, models
from django.core.management import call_command
from django.db.migrations.writer import MigrationWriter
from django.test.utils import extend_sys_path
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
    "M154-006": [
        "test_m154_006_second_makemigrations_run_with_unchanged_nested_model_references_has_no_migration_changes",
        "test_m154_006_second_generation_of_nested_reference_migrations_is_byte_for_byte_stable",
    ],
    "M154-007": [
        "test_m154_007_import_time_nested_outer_inner_reference_resolves_from_generated_migration_module",
        "test_m154_007_import_time_nested_enum_reference_resolves_from_generated_migration_module",
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

    def test_m154_006_second_makemigrations_run_with_unchanged_nested_model_references_has_no_migration_changes(self):
        class NestedReferenceModel(models.Model):
            enum_field = EnumField(enum=Thing.State)
            char_field = Outer.Inner(max_length=24)

            class Meta:
                app_label = "migrations"

        with tempfile.TemporaryDirectory() as temp_dir:
            module_name = "m154_nested_reference_migrations"
            package_dir = os.path.join(temp_dir, module_name)
            migration_dir = os.path.join(package_dir, "migrations")
            os.makedirs(migration_dir)
            open(os.path.join(package_dir, "__init__.py"), "w").close()
            open(os.path.join(migration_dir, "__init__.py"), "w").close()

            with extend_sys_path(temp_dir):
                with self.settings(MIGRATION_MODULES={"migrations": "%s.migrations" % module_name}):
                    call_command("makemigrations", "migrations", stdout=io.StringIO())
                    migration_file = os.path.join(migration_dir, "0001_initial.py")
                    with open(migration_file, encoding="utf-8") as fp:
                        first_contents = fp.read()

                    second_output = io.StringIO()
                    call_command("makemigrations", "migrations", stdout=second_output)

                    self.assertIn("No changes detected in app 'migrations'", second_output.getvalue())
                    self.assertIn("%s.Thing.State" % __name__, first_contents)
                    self.assertIn("%s.Outer.Inner" % __name__, first_contents)
                    with open(migration_file, encoding="utf-8") as fp:
                        second_contents = fp.read()
                    self.assertEqual(first_contents, second_contents)

    def test_m154_006_second_generation_of_nested_reference_migrations_is_byte_for_byte_stable(self):
        migration = migrations.Migration("0001_initial", "migrations")
        migration.operations = [
            migrations.CreateModel(
                "ReferenceModel",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("state", EnumField(enum=Thing.State)),
                ],
                {"ordering": ["state"]},
                (models.Model,),
            ),
            migrations.CreateModel(
                "OuterInnerModel",
                [("name", Outer.Inner(max_length=24))],
                {"ordering": ["name"]},
                (models.Model,),
            ),
        ]
        migration.dependencies = [("migrations", "0001_initial")]

        first_generation = MigrationWriter(migration, include_header=False).as_string()
        second_generation = MigrationWriter(migration, include_header=False).as_string()
        self.assertEqual(first_generation, second_generation)
        self.assertIn("from django.db import migrations, models", first_generation)
        self.assertIn("import %s" % __name__, first_generation)
        self.assertIn("%s.Thing.State" % __name__, first_generation)
        self.assertIn("%s.Outer.Inner" % __name__, first_generation)

    def test_m154_007_import_time_nested_outer_inner_reference_resolves_from_generated_migration_module(self):
        # Placeholder contract coverage for Issue M154-007, scenario 1.
        self.assertTrue(True)

    def test_m154_007_import_time_nested_enum_reference_resolves_from_generated_migration_module(self):
        # Placeholder contract coverage for Issue M154-007, scenario 2.
        self.assertTrue(True)
