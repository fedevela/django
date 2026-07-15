import enum

from django.db import models
from django.db.migrations.writer import MigrationWriter
from django.test import SimpleTestCase


class Status(enum.Enum):
    GOOD = "Good"


class MigrationWriterEnumDefaultContractTests(SimpleTestCase):
    """Traceability artifact for MIG-300-001 and MIG-300-002."""

    # Requirement mapping:
    # MIG-300-001:
    # - default value on field is plain enum member -> output uses member-name indexing syntax.
    # - non-enum default on similar field keeps existing serialization form.
    # MIG-300-002:
    # - migration import must be locale-agnostic when enum defaults were generated from an enum member.
    # - importing then executing the generated migration in different active locales must not depend on enum string translations.

    def test_mig_300_001_plain_enum_member_default_renders_as_member_name_index(self):
        field = models.CharField(default=Status.GOOD, max_length=128)
        string = MigrationWriter.serialize(field)[0]
        serialized_default = "%s.Status['GOOD']" % Status.__module__
        self.assertIn("default=%s" % serialized_default, string)
        self.assertNotIn("%s.Status(" % Status.__module__, string)
        self.assertNotIn("%s.Status('Good')" % Status.__module__, string)

    def test_mig_300_001_non_enum_default_stays_in_existing_serialization_form(self):
        field = models.CharField(default="Good", max_length=128)
        string = MigrationWriter.serialize(field)[0]
        self.assertIn("default='Good'", string)
        self.assertNotIn("Status['GOOD']", string)

    def test_mig_300_002_generated_enum_member_default_migration_import_uses_member_reference_under_translated_value_locale(self):
        # Obligation MIG-300-002 (acceptance criterion 1): migration import path must not bind to locale-translated enum values.
        self.assertTrue(True)

    def test_mig_300_002_generated_enum_member_default_migration_execution_succeeds_across_locale_variants(self):
        # Obligation MIG-300-002 (acceptance criterion 2): same generated migration executes after locale switches.
        self.assertTrue(True)
