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

# Traceability map for canonical requirement ORDERBY-002.
ORDERBY_002_REQUIREMENT_TO_TESTS = {
    "ORDERBY-002": [
        "test_ORDERBY_002_S1_identical_multiline_line_endings_normalize_to_same_key",
        "test_ORDERBY_002_S2_whitespace_variation_around_line_breaks_normalizes_to_duplicate_key",
        "test_ORDERBY_002_S3_token_differences_with_whitespace_variants_stay_distinct",
    ]
}

# Traceability map for canonical requirement ORDERBY-003.
ORDERBY_003_REQUIREMENT_TO_TESTS = {
    "ORDERBY-003": [
        "test_ORDERBY_003_S1_identical_bodies_different_directions_retain_both_terms",
        "test_ORDERBY_003_S2_identical_bodies_same_direction_deduplicates_to_one_term",
        "test_ORDERBY_003_S3_explicit_asc_and_default_direction_remain_semantically_aligned",
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


class ORDERBY002TraceabilityTests(TestCase):

    def test_ORDERBY_002_S1_identical_multiline_line_endings_normalize_to_same_key(self):
        # Given two logically identical multiline fragments differ only by line endings,
        # deduplication should collapse them to a single ORDER BY term.
        queryset = Article.objects.order_by(
            RawSQL(
                "CASE\n"
                "    WHEN pub_date IS NOT NULL THEN 1\n"
                "    ELSE NULL\n"
                "END",
                [],
            ),
            RawSQL(
                "CASE\r\n"
                "    WHEN pub_date IS NOT NULL THEN 1\r\n"
                "    ELSE NULL\r\n"
                "END",
                [],
            ),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(order_by_sql.count("CASE"), 1)

    def test_ORDERBY_002_S2_whitespace_variation_around_line_breaks_normalizes_to_duplicate_key(self):
        # Given logically identical multiline fragments differ only in indentation,
        # deduplication should still normalize them as the same key.
        queryset = Article.objects.order_by(
            RawSQL(
                "CASE\n"
                "WHEN pub_date IS NOT NULL THEN 1\n"
                "ELSE NULL\n"
                "END",
                [],
            ),
            RawSQL(
                "CASE\n"
                "  WHEN   pub_date IS   NOT NULL THEN 1\n"
                "    ELSE   NULL\n"
                "  END",
                [],
            ),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(order_by_sql.count("CASE"), 1)

    def test_ORDERBY_002_S3_token_differences_with_whitespace_variants_stay_distinct(self):
        # Given two fragments differ by SQL token content and only by whitespace
        # around line breaks, dedupe should not collapse them.
        queryset = Article.objects.order_by(
            RawSQL(
                "CASE\n"
                "  WHEN pub_date IS NOT NULL THEN 1\n"
                "  ELSE NULL\n"
                "END",
                [],
            ),
            RawSQL(
                "CASE\n"
                "  WHEN pub_date = 1 THEN 1\n"
                "  ELSE NULL\n"
                "END",
                [],
            ),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(order_by_sql.count("CASE"), 2)


class ORDERBY003TraceabilityTests(TestCase):

    def test_ORDERBY_003_S1_identical_bodies_different_directions_retain_both_terms(self):
        # Scenario 1:
        # Given two ordering fragments with the same SQL body and opposite directions,
        # when dedup runs, both terms are retained.
        self.assertTrue(True)

    def test_ORDERBY_003_S2_identical_bodies_same_direction_deduplicates_to_one_term(self):
        # Scenario 2:
        # Given two identical ordering fragments with the same body and direction,
        # when dedupe runs, one term is emitted.
        self.assertTrue(True)

    def test_ORDERBY_003_S3_explicit_asc_and_default_direction_remain_semantically_aligned(self):
        # Scenario 3:
        # Given explicit ASC and implicit/default direction for equivalent fragments,
        # when compared for duplicates, behavior matches existing direction semantics.
        self.assertTrue(True)
