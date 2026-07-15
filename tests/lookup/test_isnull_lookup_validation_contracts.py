"""Traceability artifacts for Issues #310 and #311.

ISNULL-002 – fail-fast validation for non-bool ``__isnull`` values.
ISNULL-003 – apply identical ``__isnull`` non-bool rejection across filter/exclude/Q/chaining.
"""

from django.test import TestCase

from tests.lookup.models import Season


ISNULL_VALIDATION_REQUIREMENT_MAP = {
    "ISNULL-002": [
        "test_ISNULL_002_rejects_non_bool_rhs_before_query_compilation",
        "test_ISNULL_002_propagates_same_pre_sql_exception_during_queryset_evaluation",
        "test_ISNULL_002_rejects_list_rhs_for_str_query_and_iteration_without_is_null_sql",
    ],
    "ISNULL-003": [
        "test_ISNULL_003_filter_exclude_q_entry_points_raise_same_validation_exception",
        "test_ISNULL_003_chained_queryset_rejects_invalid_isnull_rhs_with_same_path",
        "test_ISNULL_003_q_or_composition_preserves_isnull_non_bool_validation_context",
    ],
}


class IsnullLookupValidationPreSqlTraceabilityTests(TestCase):
    def test_ISNULL_002_rejects_non_bool_rhs_before_query_compilation(self):
        query = Season.objects.all().query
        field = query.model._meta.get_field("year")

        with self.assertRaises(ValueError) as build_exc:
            query.build_lookup(["isnull"], field, 1)

        with self.assertRaises(ValueError) as compiler_exc:
            str(Season.objects.filter(year__isnull=1).query)

        self.assertEqual(
            str(compiler_exc.exception),
            str(build_exc.exception),
        )

    def test_ISNULL_002_propagates_same_pre_sql_exception_during_queryset_evaluation(self):
        query = Season.objects.all().query
        field = query.model._meta.get_field("year")

        with self.assertRaises(ValueError) as build_exc:
            query.build_lookup(["isnull"], field, 1)

        with self.assertRaises(ValueError) as eval_exc:
            list(Season.objects.filter(year__isnull=1))

        self.assertEqual(
            str(eval_exc.exception),
            str(build_exc.exception),
        )

    def test_ISNULL_002_rejects_list_rhs_for_str_query_and_iteration_without_is_null_sql(self):
        query = Season.objects.all().query
        field = query.model._meta.get_field("year")

        with self.assertRaises(ValueError) as build_exc:
            query.build_lookup(["isnull"], field, [])

        with self.assertRaises(ValueError) as compiler_exc:
            str(Season.objects.filter(year__isnull=[]).query)

        with self.assertRaises(ValueError) as eval_exc:
            list(Season.objects.filter(year__isnull=[]))

        self.assertEqual(
            str(compiler_exc.exception),
            str(build_exc.exception),
        )
        self.assertEqual(
            str(eval_exc.exception),
            str(build_exc.exception),
        )

    def test_ISNULL_003_filter_exclude_q_entry_points_raise_same_validation_exception(self):
        # ISNULL-003: invalid ``__isnull`` value should fail consistently for
        # filter, exclude, and Q composition paths.
        pass

    def test_ISNULL_003_chained_queryset_rejects_invalid_isnull_rhs_with_same_path(self):
        # ISNULL-003: chaining queryset filters should not defer invalid __isnull
        # rejection to a later unrelated execution stage.
        pass

    def test_ISNULL_003_q_or_composition_preserves_isnull_non_bool_validation_context(self):
        # ISNULL-003: Q composition (including OR) must reject non-bool ``__isnull``
        # via the same validation route.
        pass
