from django.db.models import F, RawSQL
from django.test import TestCase

from tests.expressions.models import Company, Employee

from .models import Article


# Traceability map for canonical requirement ORDERBY-007.
ORDERBY_007_REQUIREMENT_TO_TESTS = {
    "ORDERBY-007": [
        "test_ORDERBY_007_S1_single_line_dedupe_semantics_unchanged_baseline_contract",
        "test_ORDERBY_007_S2_multiline_trailing_line_collision_keeps_expected_clauses",
        "test_ORDERBY_007_S3_multiline_newline_variants_crlf_lf_cr_normalized_stable_dedupe",
        "test_ORDERBY_007_S4_true_duplicate_multiline_terms_emits_once",
        "test_ORDERBY_007_S5_regression_contracts_test_order_by_multiline_sql_and_test_order_of_operations",
    ]
}


# Existing baseline verification loci that already exercise adjacent behavior.
ORDERBY_007_BASELINE_TEST_LINKS = {
    "single-line-dedupe-unchanged": "tests/ordering/tests.py::OrderingTests.test_order_by_f_expression_duplicates",
    "multiline-sql": "tests/ordering/tests.py::OrderingTests.test_order_by_multiline_sql",
    "order-of-operations-regression": "tests/expressions/tests.py::ExpressionTests.test_order_of_operations",
}


class ORDERBY007TraceabilityTests(TestCase):
    @staticmethod
    def _extract_order_by_clause(queryset):
        return str(queryset.query).upper().split("ORDER BY", 1)[1]

    def test_ORDERBY_007_S1_single_line_dedupe_semantics_unchanged_baseline_contract(self):
        """
        ORDERBY-007-S1: preserve existing single-line dedupe behavior.
        """
        queryset = Article.objects.order_by(F("headline").asc(), F("headline").desc())
        order_by_sql = self._extract_order_by_clause(queryset)
        self.assertEqual(order_by_sql.count("HEADLINE"), 1)

        queryset = Article.objects.order_by(F("headline").desc(), F("headline").asc())
        order_by_sql = self._extract_order_by_clause(queryset)
        self.assertEqual(order_by_sql.count("HEADLINE"), 1)

    def test_ORDERBY_007_S2_multiline_trailing_line_collision_keeps_expected_clauses(self):
        """
        ORDERBY-007-S2: collisions on trailing multiline lines must not collapse distinct terms.
        """
        queryset = Article.objects.order_by(
            RawSQL(
                """
                CASE
                    WHEN headline LIKE 'Article %' THEN 1
                    ELSE 0
                END
                """,
                [],
            ),
            RawSQL(
                """
                CASE
                    WHEN pub_date IS NOT NULL THEN 1
                    ELSE 0
                END
                """,
                [],
            ),
        )
        order_by_sql = self._extract_order_by_clause(queryset)
        self.assertIn("WHEN HEADLINE LIKE 'ARTICLE %' THEN 1", order_by_sql)
        self.assertIn("WHEN PUB_DATE IS NOT NULL THEN 1", order_by_sql)
        self.assertEqual(order_by_sql.count("CASE"), 2)

    def test_ORDERBY_007_S3_multiline_newline_variants_crlf_lf_cr_normalized_stable_dedupe(self):
        """
        ORDERBY-007-S3: normalize LF/CRLF/CR variants before dedupe.
        """
        fragment = (
            "CASE\n"
            "    WHEN pub_date IS NOT NULL THEN 1\n"
            "    ELSE 0\n"
            "END"
        )
        queryset = Article.objects.order_by(
            RawSQL(fragment, []),
            RawSQL(fragment.replace("\n", "\r\n"), []),
            RawSQL(fragment.replace("\n", "\r"), []),
        )
        order_by_sql = self._extract_order_by_clause(queryset)
        self.assertEqual(order_by_sql.count("CASE"), 1)

    def test_ORDERBY_007_S4_true_duplicate_multiline_terms_emits_once(self):
        """
        ORDERBY-007-S4: exact duplicate multiline clauses should emit once.
        """
        queryset = Article.objects.order_by(
            RawSQL(
                """
                CASE
                    WHEN pub_date IS NOT NULL THEN 1
                    ELSE 0
                END
                """,
                [],
            ),
            RawSQL(
                """
                CASE
                    WHEN pub_date IS NOT NULL THEN 1
                    ELSE 0
                END
                """,
                [],
            ),
            RawSQL(
                """
                CASE
                    WHEN headline = 'x' THEN 1
                    ELSE 0
                END
                """,
                [],
            ),
        )
        order_by_sql = self._extract_order_by_clause(queryset)
        self.assertEqual(order_by_sql.count("CASE"), 2)

    def test_ORDERBY_007_S5_regression_contracts_test_order_by_multiline_sql_and_test_order_of_operations(self):
        """
        ORDERBY-007-S5: preserve multiline-ordering and expression order-of-operations behavior.
        """
        queryset = Article.objects.order_by(
            RawSQL(
                "CASE\nWHEN headline LIKE 'Article %' THEN 1\nELSE 0\nEND",
                [],
            ),
            RawSQL(
                "CASE\nWHEN pub_date IS NOT NULL THEN 1\nELSE 0\nEND",
                [],
            ),
        )
        order_by_sql = self._extract_order_by_clause(queryset)
        self.assertEqual(order_by_sql.count("CASE"), 2)
        self.assertIn("CASE\nWHEN HEADLINE LIKE 'ARTICLE %' THEN 1", order_by_sql)
        self.assertIn("CASE\nWHEN PUB_DATE IS NOT NULL THEN 1", order_by_sql)

        employee = Employee.objects.create(firstname="Joe", lastname="Smith", salary=10)
        company = Company.objects.create(
            name="Acme",
            num_employees=4,
            num_chairs=1,
            ceo=employee,
            point_of_contact=employee,
        )
        company2 = Company.objects.create(
            name="Beta",
            num_employees=7,
            num_chairs=2,
            ceo=employee,
            point_of_contact=employee,
        )
        Company.objects.filter(id__in=[company.id, company2.id]).update(
            num_chairs=F("num_employees") + 2 * F("num_employees")
        )
        self.assertEqual(Company.objects.get(id=company.id).num_chairs, 12)
        self.assertEqual(Company.objects.get(id=company2.id).num_chairs, 21)
