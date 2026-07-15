import enum

from django.db import models
from django.db.migrations.writer import MigrationWriter
from django.test import SimpleTestCase


class Status(enum.Enum):
    GOOD = "Good"


class MigrationWriterEnumDefaultContractTests(SimpleTestCase):
    """Traceability artifact for MIG-300-001."""

    # Requirement mapping:
    # MIG-300-001:
    # - default value on field is plain enum member -> output uses member-name indexing syntax.
    # - non-enum default on similar field keeps existing serialization form.

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
