import enum

from django.db import migrations, models
from django.db.migrations.state import ProjectState
from django.db.migrations.writer import MigrationWriter
from django.test import SimpleTestCase
from django.utils.functional import lazy
from django.utils.translation import get_language, override


class PlainStatus(enum.Enum):
    GOOD = "Good"


def _locale_aware_status_value():
    return {
        "en": "Good",
        "fr": "Bien",
    }.get(get_language() or "en", "Good")


class LocaleAwareStatus(models.TextChoices):
    GOOD = lazy(_locale_aware_status_value, str)()


class LocaleValueAwareStatus(enum.Enum):
    GOOD = lazy(_locale_aware_status_value, str)()


def _mixed_default_callable():
    return "mixed-defaults-callable"


class StringShapedPayload(str):
    """Serializable non-enum value that mimics enum-name-shaped payloads."""

    pass


class MigrationWriterEnumDefaultContractTests(SimpleTestCase):
    """Traceability artifact for MIG-300-001, MIG-300-002, and MIG-300-003."""

    # Requirement mapping:
    # MIG-300-001:
    # - default value on field is plain enum member -> output uses member-name indexing syntax.
    # - non-enum default on similar field keeps existing serialization form.
    # MIG-300-002:
    # - migration import must be locale-agnostic when enum defaults were generated from an enum member.
    # - importing then executing the generated migration in different active locales must not depend on enum string translations.
    # MIG-300-003:
    # - generated migration defaults must deserialize to the same enum member object as source defaults.
    # - identity must remain stable across locale switches between generation and import.

    def _locale_sensitive_migration_text(self):
        field = models.CharField(
            default=LocaleAwareStatus.GOOD,
            max_length=16,
            choices=LocaleAwareStatus.choices,
        )
        migration = type("Migration", (migrations.Migration,), {
            "operations": [
                migrations.CreateModel(
                    "StatusModel",
                    fields=(("status", field),),
                    bases=(models.Model,),
                ),
            ],
            "dependencies": [],
        })
        return MigrationWriter(migration).as_string()

    def _load_migration_module(self, migration_text):
        namespace = {}
        exec(migration_text, globals(), namespace)
        return namespace

    def test_mig_300_001_plain_enum_member_default_renders_as_member_name_index(self):
        field = models.CharField(default=PlainStatus.GOOD, max_length=128)
        string = MigrationWriter.serialize(field)[0]
        serialized_default = "%s.PlainStatus['GOOD']" % PlainStatus.__module__
        self.assertIn("default=%s" % serialized_default, string)
        self.assertNotIn("%s.PlainStatus(" % PlainStatus.__module__, string)
        self.assertNotIn("%s.PlainStatus('Good')" % PlainStatus.__module__, string)

    def test_mig_300_001_non_enum_default_stays_in_existing_serialization_form(self):
        field = models.CharField(default="Good", max_length=128)
        string = MigrationWriter.serialize(field)[0]
        self.assertIn("default='Good'", string)
        self.assertNotIn("PlainStatus['GOOD']", string)

    def test_mig_300_002_generated_enum_member_default_migration_import_uses_member_reference_under_translated_value_locale(self):
        with override("en"):
            migration_text = self._locale_sensitive_migration_text()

        serialized_default = "%s.LocaleAwareStatus['GOOD']" % LocaleAwareStatus.__module__
        self.assertIn("default=%s" % serialized_default, migration_text)
        self.assertNotIn("default='Good'", migration_text)
        self.assertNotIn("default='Bien'", migration_text)

        with override("fr"):
            try:
                self._load_migration_module(migration_text)
            except ValueError as exc:
                self.fail("Unexpected ValueError when importing migration under FR locale: %s" % exc)

    def test_mig_300_002_generated_enum_member_default_migration_execution_succeeds_across_locale_variants(self):
        with override("en"):
            migration_text = self._locale_sensitive_migration_text()

        for language in ["en", "fr"]:
            with override(language):
                namespace = self._load_migration_module(migration_text)
                migration = namespace["Migration"]("0001", "locale_status")
                state = ProjectState()
                for operation in migration.operations:
                    operation.state_forwards("locale_status", state)
                fields = dict(state.models["locale_status", "statusmodel"].fields)
                self.assertIs(fields["status"].default, LocaleAwareStatus.GOOD)

    def test_mig_300_003_imported_enum_default_preserves_source_member_identity(self):
        field = models.CharField(default=PlainStatus.GOOD, max_length=16)
        migration = type(
            "Migration", (migrations.Migration,), {
                "operations": [
                    migrations.CreateModel(
                        "StatusModel",
                        fields=(("status", field),),
                        bases=(models.Model,),
                    ),
                ],
                "dependencies": [],
            }
        )
        migration_text = MigrationWriter(migration).as_string()
        self.assertIn("%s.PlainStatus['GOOD']" % PlainStatus.__module__, migration_text)

        for language in ("en", "fr"):
            with override(language):
                namespace = self._load_migration_module(migration_text)
                migration_instance = namespace["Migration"]("0001", "status")
                state = ProjectState()
                for operation in migration_instance.operations:
                    operation.state_forwards("status", state)
                fields = dict(state.models["status", "statusmodel"].fields)
                self.assertIs(fields["status"].default, PlainStatus.GOOD)

    def test_mig_300_003_enum_member_identity_survives_locale_change_between_generation_and_import(self):
        with override("en"):
            migration_text = self._locale_sensitive_migration_text()
        for language in ["fr", "en"]:
            with override(language):
                namespace = self._load_migration_module(migration_text)
                migration_instance = namespace["Migration"]("0001", "locale_status")
                state = ProjectState()
                for operation in migration_instance.operations:
                    operation.state_forwards("locale_status", state)
                fields = dict(state.models["locale_status", "statusmodel"].fields)
                self.assertIs(fields["status"].default, LocaleAwareStatus.GOOD)


class MigrationWriterEnumDefaultDeterminismContractsTests(SimpleTestCase):
    """Traceability placeholders for MIG-300-004."""

    # MIG-300-004 obligations:
    # - AC1: repeated autogeneration must stay on member-index form across locale switches.
    # - AC2: enum default deconstruction/reconstruction stays stable on Locale-sensitive enum values.

    def _locale_sensitive_migration_text(self):
        field = models.CharField(
            default=LocaleValueAwareStatus.GOOD,
            max_length=16,
        )
        migration = type("Migration", (migrations.Migration,), {
            "operations": [
                migrations.CreateModel(
                    "StatusModel",
                    fields=(("status", field),),
                    bases=(models.Model,),
                ),
            ],
            "dependencies": [],
        })
        return MigrationWriter(migration, include_header=False).as_string()

    def _expected_enum_default_fragment(self):
        return "%s.LocaleValueAwareStatus['GOOD']" % LocaleValueAwareStatus.__module__

    def test_mig_300_004_locale_round_trip_repeated_autogeneration_keeps_enum_member_index_text(self):
        expected_fragment = self._expected_enum_default_fragment()
        generated_text = []
        for language in ("en", "fr", "en"):
            with override(language):
                migration_text = self._locale_sensitive_migration_text()
            self.assertIn("default=%s" % expected_fragment, migration_text)
            self.assertNotIn("default='Good'", migration_text)
            self.assertNotIn("default='Bien'", migration_text)
            generated_text.append(migration_text)

        self.assertEqual(generated_text[0], generated_text[1], "Locale A->B must not alter enum-default migration text.")
        self.assertEqual(generated_text[1], generated_text[2], "Locale A->B->A must remain byte-stable for enum-default output.")

    def test_mig_300_004_deconstruction_reconstruction_stable_enum_class_member_form(self):
        expected_fragment = self._expected_enum_default_fragment()
        serialized_by_locale = []
        for language in ("en", "fr"):
            with override(language):
                field = models.CharField(
                    default=LocaleValueAwareStatus.GOOD,
                    max_length=16,
                )
                serialized_field = MigrationWriter.serialize(field)[0]
            self.assertIn("default=%s" % expected_fragment, serialized_field)
            self.assertNotIn("default='Good'", serialized_field)
            self.assertNotIn("default='Bien'", serialized_field)
            serialized_by_locale.append(serialized_field)

        self.assertEqual(serialized_by_locale[0], serialized_by_locale[1], "Deconstruction/reconstruction must remain stable across locale variants.")


class MigrationWriterEnumDefaultMixedDefaultsContractsTests(SimpleTestCase):
    """Executable verification for MIG-300-005 mixed default serialization."""

    # MIG-300-005 obligations:
    # - In mixed-default migrations, only plain enum.Enum defaults may use
    #   member-name syntax for serialization.
    # - Non-enum defaults (callable, string, number, etc.) must keep existing
    #   serializer output unchanged.
    # - Non-enum objects with string-shaped payloads must never be rewritten
    #   into enum member indexing.

    def test_mig_300_005_mixed_defaults_only_plain_enums_use_member_name_serialization(self):
        migration_text = MigrationWriter(
            type(
                "Migration",
                (migrations.Migration,),
                {
                    "operations": [
                        migrations.CreateModel(
                            "StatusModel",
                            fields=(
                                ("status", models.CharField(default=PlainStatus.GOOD, max_length=16)),
                                ("status_text", models.CharField(default="x", max_length=16)),
                                ("status_code", models.IntegerField(default=42)),
                                ("status_callable", models.CharField(default=_mixed_default_callable, max_length=16)),
                            ),
                            bases=(models.Model,),
                        ),
                    ],
                    "dependencies": [],
                },
            ),
            include_header=False,
        ).as_string()

        expected_enum_fragment = "%s.PlainStatus['GOOD']" % PlainStatus.__module__
        expected_callable_fragment = "%s._mixed_default_callable" % __name__
        self.assertIn("default=%s" % expected_enum_fragment, migration_text)
        self.assertIn("default='x'", migration_text)
        self.assertIn("default=42", migration_text)
        self.assertIn("default=%s" % expected_callable_fragment, migration_text)
        self.assertNotIn("default=\"x\"", migration_text)
        self.assertNotIn("default=PlainStatus('Good')", migration_text)

    def test_mig_300_005_non_enum_defaults_in_mixed_payloads_keep_original_form(self):
        migration_text = MigrationWriter(
            type(
                "Migration",
                (migrations.Migration,),
                {
                    "operations": [
                        migrations.CreateModel(
                            "StatusModel",
                            fields=(
                                ("status", models.CharField(default=PlainStatus.GOOD, max_length=16)),
                                ("status_text", models.CharField(default="x", max_length=16)),
                                ("status_code", models.IntegerField(default=42)),
                                ("status_callable", models.CharField(default=_mixed_default_callable, max_length=16)),
                            ),
                            bases=(models.Model,),
                        ),
                    ],
                    "dependencies": [],
                },
            ),
            include_header=False,
        ).as_string()

        self.assertIn("default=%s.PlainStatus['GOOD']" % PlainStatus.__module__, migration_text)
        self.assertIn("default='x'", migration_text)
        self.assertIn("default=42", migration_text)
        self.assertIn("default=%s._mixed_default_callable" % __name__, migration_text)

    def test_mig_300_005_non_enum_object_matching_string_shape_avoids_enum_syntax_rewrite(self):
        migration_text = MigrationWriter(
            type(
                "Migration",
                (migrations.Migration,),
                {
                    "operations": [
                        migrations.CreateModel(
                            "StatusModel",
                            fields=(
                                ("status", models.CharField(default=PlainStatus.GOOD, max_length=16)),
                                ("status_text", models.CharField(default=StringShapedPayload("GOOD"), max_length=16)),
                            ),
                            bases=(models.Model,),
                        ),
                    ],
                    "dependencies": [],
                },
            ),
            include_header=False,
        ).as_string()

        self.assertIn("status=models.CharField(default=%s.PlainStatus['GOOD'], max_length=16)" % PlainStatus.__module__, migration_text)
        self.assertIn("default=%s.PlainStatus['GOOD']" % PlainStatus.__module__, migration_text)
        self.assertIn("default='GOOD'", migration_text)
        self.assertNotIn("status_text=models.CharField(default=%s.PlainStatus['GOOD']" % PlainStatus.__module__, migration_text)
