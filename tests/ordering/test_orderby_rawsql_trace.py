from django.db import connection
from django.db.models import F, OrderBy, RawSQL
from django.test import TestCase

from .models import Article


class _MalformedDirectionOrderBy(OrderBy):
    def __init__(self, expression, suffix):
        super().__init__(expression)
        self.suffix = suffix

    def as_sql(self, compiler, connection, template=None, **extra_context):
        expression_sql, params = compiler.compile(self.expression)
        return f"{expression_sql}{self.suffix}", params


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
        fragment = """
            CASE
                WHEN pub_date IS NOT NULL THEN 1
                ELSE NULL
            END
        """
        queryset = Article.objects.order_by(
            RawSQL(fragment, []).asc(),
            RawSQL(fragment, []).desc(),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(order_by_sql.count("CASE"), 2)
        self.assertIn("ASC", order_by_sql.upper())
        self.assertIn("DESC", order_by_sql.upper())

    def test_ORDERBY_003_S2_identical_bodies_same_direction_deduplicates_to_one_term(self):
        # Scenario 2:
        # Given two identical ordering fragments with the same body and direction,
        # when dedupe runs, one term is emitted.
        fragment = """
            CASE
                WHEN pub_date IS NOT NULL THEN 1
                ELSE NULL
            END
        """
        queryset = Article.objects.order_by(
            RawSQL(fragment, []).desc(),
            RawSQL(fragment, []).desc(),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(order_by_sql.count("CASE"), 1)
        self.assertIn("DESC", order_by_sql.upper())

    def test_ORDERBY_003_S3_explicit_asc_and_default_direction_remain_semantically_aligned(self):
        # Scenario 3:
        # Given explicit ASC and implicit/default direction for equivalent fragments,
        # when compared for duplicates, behavior matches existing direction semantics.
        fragment = """
            CASE
                WHEN pub_date IS NOT NULL THEN 1
                ELSE NULL
            END
        """
        queryset = Article.objects.order_by(
            RawSQL(fragment, []).asc(),
            RawSQL(fragment, []),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(order_by_sql.count("CASE"), 1)


# Traceability map for canonical requirement ORDERBY-004.
ORDERBY_004_REQUIREMENT_TO_TESTS = {
    "ORDERBY-004": [
        "test_ORDERBY_004_S1_rawsql_and_non_rawsql_terms_share_normalized_fragment_keying",
        "test_ORDERBY_004_S2_non_rawsql_semantically_identical_duplicates_drop_to_one_term",
        "test_ORDERBY_004_S3_type_and_body_differences_prevent_cross_type_collision",
    ]
}


# Traceability map for canonical requirement ORDERBY-005.
ORDERBY_005_REQUIREMENT_TO_TESTS = {
    "ORDERBY-005": [
        "test_ORDERBY_005_S1_malformed_direction_text_falls_back_to_single_emission",
        "test_ORDERBY_005_S2_identical_malformed_terms_emit_once_in_dedupe_pass",
        "test_ORDERBY_005_S3_malformed_and_parseable_equivalent_terms_stay_distinct_without_collision",
    ]
}


class ORDERBY004TraceabilityTests(TestCase):

    @staticmethod
    def _quoted_headline_ref():
        table = connection.ops.quote_name(Article._meta.db_table)
        column = connection.ops.quote_name(Article._meta.get_field('headline').column)
        return f"{table}.{column}"

    def test_ORDERBY_004_S1_rawsql_and_non_rawsql_terms_share_normalized_fragment_keying(self):
        # Scenario 1:
        # Given a mix of RawSQL and non-RawSQL ordering expressions,
        # then both are represented by the same normalized dedupe keying path.
        heading_ref = self._quoted_headline_ref()
        queryset = Article.objects.order_by(
            F("headline"),
            RawSQL(heading_ref, []),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(len(order_by_sql.split(",")), 1)

    def test_ORDERBY_004_S2_non_rawsql_semantically_identical_duplicates_drop_to_one_term(self):
        # Scenario 2:
        # Given duplicate non-RawSQL terms are semantically identical,
        # then duplicate elimination leaves exactly one matching clause.
        queryset = Article.objects.order_by(
            F("headline").desc(),
            F("headline").desc(),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(len(order_by_sql.split(",")), 1)
        self.assertIn("DESC", order_by_sql.upper())

    def test_ORDERBY_004_S3_type_and_body_differences_prevent_cross_type_collision(self):
        # Scenario 3:
        # Given similar clause bodies across expression types with different semantics,
        # then only exact body+direction duplicates are removed.
        heading_ref = self._quoted_headline_ref()
        queryset = Article.objects.order_by(
            F("headline").desc(),
            RawSQL(f"{heading_ref} ASC", []),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(len(order_by_sql.split(",")), 2)
        self.assertIn("DESC", order_by_sql.upper())
        self.assertIn("ASC", order_by_sql.upper())


class ORDERBY005TraceabilityTests(TestCase):

    def test_ORDERBY_005_S1_malformed_direction_text_falls_back_to_single_emission(self):
        """
        Scenario 1:
        Given malformed/irregular direction text for an ordering term,
        when duplicate suppression evaluates the dedupe key,
        then the term is emitted once instead of being dropped.
        """
        queryset = Article.objects.order_by(
            _MalformedDirectionOrderBy(F("headline"), " DESCENDING"),
            _MalformedDirectionOrderBy(F("headline"), " DESCENDING"),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(len(order_by_sql.split(",")), 1)
        self.assertIn("DESCENDING", order_by_sql.upper())

    def test_ORDERBY_005_S2_identical_malformed_terms_emit_once_in_dedupe_pass(self):
        """
        Scenario 2:
        Given duplicate malformed terms,
        when duplicate suppression executes,
        then only one emission occurs deterministically.
        """
        queryset = Article.objects.order_by(
            _MalformedDirectionOrderBy(F("headline"), " DESCENDING"),
            _MalformedDirectionOrderBy(F("headline"), "  DESCENDING"),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(len(order_by_sql.split(",")), 1)
        self.assertEqual(order_by_sql.upper().count("DESCENDING"), 1)

    def test_ORDERBY_005_S3_malformed_and_parseable_equivalent_terms_stay_distinct_without_collision(self):
        """
        Scenario 3:
        Given malformed and parseable equivalent terms,
        when dedupe compares keys,
        then fallback handling is deterministic with no accidental omission.
        """
        queryset = Article.objects.order_by(
            _MalformedDirectionOrderBy(F("headline"), ""),
            F("headline"),
        )
        order_by_sql = str(queryset.query).split("ORDER BY", 1)[1]
        self.assertEqual(len(order_by_sql.split(",")), 2)
        self.assertIn("ASC", order_by_sql.upper())
        self.assertIn("DESCENDING", order_by_sql.upper())
