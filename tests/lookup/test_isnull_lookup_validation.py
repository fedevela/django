"""
Traceability artifacts for Issue #309:
ISNULL-001 and ISNULL-005.

These are schema-level placeholders for lookup-resolution validation behavior.
"""

from django.db.models.lookups import IsNull
from django.test import SimpleTestCase

from tests.lookup.models import Season


ISNULL_VALIDATION_REQUIREMENT_MAP = {
    "ISNULL-001": [
        "test_isnull_001_rejects_non_boolean_rhs_values_before_evaluation",
        "test_isnull_001_allows_boolean_true_or_false_rhs_without_rejection",
    ],
    "ISNULL-005": [
        "test_isnull_005_uses_lookup_validation_exception_family",
        "test_isnull_005_includes_isnull_and_invalid_type_in_validation_context",
    ],
}


class IsnullLookupValidationTraceabilityTests(SimpleTestCase):
    def test_isnull_001_rejects_non_boolean_rhs_values_before_evaluation(self):
        # ISNULL-001
        query = Season.objects.all().query
        field = query.model._meta.get_field("year")
        for rhs in (1, 0, "1", [], {}, object(), None):
            with self.subTest(rhs=rhs):
                with self.assertRaises(ValueError):
                    query.build_lookup(["isnull"], field, rhs)

    def test_isnull_001_allows_boolean_true_or_false_rhs_without_rejection(self):
        # ISNULL-001
        query = Season.objects.all().query
        field = query.model._meta.get_field("year")
        for rhs in (True, False):
            with self.subTest(rhs=rhs):
                lookup = query.build_lookup(["isnull"], field, rhs)
                self.assertIsInstance(lookup, IsNull)

    def test_isnull_005_uses_lookup_validation_exception_family(self):
        # ISNULL-005
        query = Season.objects.all().query
        field = query.model._meta.get_field("year")
        with self.assertRaises(ValueError):
            query.build_lookup(["isnull"], field, 1)

    def test_isnull_005_includes_isnull_and_invalid_type_in_validation_context(self):
        # ISNULL-005
        query = Season.objects.all().query
        field = query.model._meta.get_field("year")
        with self.assertRaises(ValueError) as exc:
            query.build_lookup(["isnull"], field, "1")
        message = str(exc.exception)
        self.assertIn("__isnull", message)
        self.assertIn("str", message)
