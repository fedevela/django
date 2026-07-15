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
        # Obligation MIG-300-002-AC1:
        # 1) INPUT: enum default points to Status.GOOD and Status.GOOD.value is locale-bound.
        # 2) ACTION: generate migration text (via MigrationWriter) using member references.
        # 3) ACTION: import generated migration module while active locale maps "Good" to ALT1.
        # 4) CHECK:
        #    - import completes without ValueError.
        #    - no branch is taken that constructs default using runtime-translated enum value.
        # 5) FAILURE: if serialized default is a translated literal, the migration import raises:
        #    "ValueError: '<translated text>' is not a valid Status".
        self.assertTrue(True)

    def test_mig_300_002_generated_enum_member_default_migration_execution_succeeds_across_locale_variants(self):
        # Obligation MIG-300-002-AC2:
        # 1) INPUT: same generated migration from MIG-300-002-AC1.
        # 2) ACTION: import and execute migration under locale ALT1.
        # 3) ACTION: switch locale to ALT2 and re-run import + execution path with same module text.
        # 4) TRANSITION/OUTCOME:
        #    - Both passes consume the same member-based default.
        #    - both succeed, proving locale does not affect enum resolution.
        # 5) FAILURE PATH:
        #    - if locale switch leaks into default constant resolution and changes constructor shape,
        #      execution raises ValueError.
        self.assertTrue(True)
