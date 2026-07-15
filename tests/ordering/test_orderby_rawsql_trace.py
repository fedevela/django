from django.db.models import RawSQL
from django.test import TestCase

from .models import Article


# Traceability map for canonical requirement ORDERBY-001.
ORDERBY_001_REQUIREMENT_TO_TESTS = {
    "ORDERBY-001": [
        "test_ORDERBY_001_S1_full_multiline_fragment_distinct_terms_preserved",
        "test_ORDERBY_001_S2_indent_variation_normalized_as_duplicate",
        "test_ORDERBY_001_S3_full_fragment_exact_match_only",
    ]
}


class ORDERBY001TraceabilityTests(TestCase):

    def test_ORDERBY_001_S1_full_multiline_fragment_distinct_terms_preserved(self):
        """
        Scenario 1: verify distinct multiline SQL fragments remain separately emitted.
        """
        queryset = Article.objects.order_by(
            RawSQL(
                """
                CASE
                    WHEN pub_date IS NOT NULL THEN 1
                    ELSE NULL
                END
                """,
                [],
            ),
            RawSQL(
                """
                CASE
                    WHEN pub_date IS NULL THEN 1
                    ELSE NULL
                END
                """,
                [],
            ),
            RawSQL(
                """
                CASE
                    WHEN headline = 'x' THEN 1
                    ELSE NULL
                END
                """,
                [],
            ),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertIn("WHEN pub_date IS NOT NULL THEN 1", order_by_sql)
        self.assertIn("WHEN pub_date IS NULL THEN 1", order_by_sql)
        self.assertIn("WHEN headline = 'x' THEN 1", order_by_sql)
        self.assertEqual(order_by_sql.count("CASE"), 3)

    def test_ORDERBY_001_S2_indent_variation_normalized_as_duplicate(self):
        """
        Scenario 2: verify normalized multiline equivalent fragments map to one duplicate key.
        """
        queryset = Article.objects.order_by(
            RawSQL(
                """
                CASE
                    WHEN pub_date IS NOT NULL THEN 1
                    ELSE NULL
                END
                """,
                [],
            ),
            RawSQL(
                """
                CASE
                  WHEN pub_date IS NOT NULL THEN 1
                ELSE NULL
                END
                """,
                [],
            ),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(order_by_sql.count("CASE"), 1)

    def test_ORDERBY_001_S3_full_fragment_exact_match_only(self):
        """
        Scenario 3: verify only exact full fragments collapse, not matching-only tails.
        """
        queryset = Article.objects.order_by(
            RawSQL(
                """
                CASE
                    WHEN pub_date IS NOT NULL THEN 1
                    ELSE NULL
                END
                """,
                [],
            ),
            RawSQL("CASE WHEN headline = 'x' THEN 1 ELSE NULL END", []),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertIn("WHEN pub_date IS NOT NULL THEN 1", order_by_sql)
        self.assertIn("WHEN headline = 'x' THEN 1", order_by_sql)
        self.assertEqual(order_by_sql.count("CASE"), 2)
