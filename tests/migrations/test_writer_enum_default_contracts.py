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


class MigrationWriterEnumDefaultContractTests(SimpleTestCase):
    """Traceability artifact for MIG-300-001 and MIG-300-002."""

    # Requirement mapping:
    # MIG-300-001:
    # - default value on field is plain enum member -> output uses member-name indexing syntax.
    # - non-enum default on similar field keeps existing serialization form.
    # MIG-300-002:
    # - migration import must be locale-agnostic when enum defaults were generated from an enum member.
    # - importing then executing the generated migration in different active locales must not depend on enum string translations.

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
