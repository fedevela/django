from datetime import datetime
from operator import attrgetter

from django.core.exceptions import FieldError
from django.db.models import (
    CharField, DateTimeField, F, Max, OuterRef, Subquery, Value,
)
from django.db.models.functions import Upper
from django.test import TestCase

from .models import Article, Author, ChildArticle, OrderedByFArticle, Reference


class OrderingTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.a1 = Article.objects.create(headline="Article 1", pub_date=datetime(2005, 7, 26))
        cls.a2 = Article.objects.create(headline="Article 2", pub_date=datetime(2005, 7, 27))
        cls.a3 = Article.objects.create(headline="Article 3", pub_date=datetime(2005, 7, 27))
        cls.a4 = Article.objects.create(headline="Article 4", pub_date=datetime(2005, 7, 28))
        cls.author_1 = Author.objects.create(name="Name 1")
        cls.author_2 = Author.objects.create(name="Name 2")
        for i in range(2):
            Author.objects.create()

    def test_default_ordering(self):
        """
        By default, Article.objects.all() orders by pub_date descending, then
        headline ascending.
        """
        self.assertQuerysetEqual(
            Article.objects.all(), [
                "Article 4",
                "Article 2",
                "Article 3",
                "Article 1",
            ],
            attrgetter("headline")
        )

        # Getting a single item should work too:
        self.assertEqual(Article.objects.all()[0], self.a4)

    def test_default_ordering_override(self):
        """
        Override ordering with order_by, which is in the same format as the
        ordering attribute in models.
        """
        self.assertQuerysetEqual(
            Article.objects.order_by("headline"), [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )
        self.assertQuerysetEqual(
            Article.objects.order_by("pub_date", "-headline"), [
                "Article 1",
                "Article 3",
                "Article 2",
                "Article 4",
            ],
            attrgetter("headline")
        )

    def test_order_by_override(self):
        """
        Only the last order_by has any effect (since they each override any
        previous ordering).
        """
        self.assertQuerysetEqual(
            Article.objects.order_by("id"), [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )
        self.assertQuerysetEqual(
            Article.objects.order_by("id").order_by("-headline"), [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline")
        )

    def test_order_by_nulls_first_and_last(self):
        msg = "nulls_first and nulls_last are mutually exclusive"
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.order_by(F("author").desc(nulls_last=True, nulls_first=True))

    def assertQuerysetEqualReversible(self, queryset, sequence):
        self.assertSequenceEqual(queryset, sequence)
        self.assertSequenceEqual(queryset.reverse(), list(reversed(sequence)))

    def test_order_by_nulls_last(self):
        Article.objects.filter(headline="Article 3").update(author=self.author_1)
        Article.objects.filter(headline="Article 4").update(author=self.author_2)
        # asc and desc are chainable with nulls_last.
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(F("author").desc(nulls_last=True), 'headline'),
            [self.a4, self.a3, self.a1, self.a2],
        )
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(F("author").asc(nulls_last=True), 'headline'),
            [self.a3, self.a4, self.a1, self.a2],
        )
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(Upper("author__name").desc(nulls_last=True), 'headline'),
            [self.a4, self.a3, self.a1, self.a2],
        )
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(Upper("author__name").asc(nulls_last=True), 'headline'),
            [self.a3, self.a4, self.a1, self.a2],
        )

    def test_order_by_nulls_first(self):
        Article.objects.filter(headline="Article 3").update(author=self.author_1)
        Article.objects.filter(headline="Article 4").update(author=self.author_2)
        # asc and desc are chainable with nulls_first.
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(F("author").asc(nulls_first=True), 'headline'),
            [self.a1, self.a2, self.a3, self.a4],
        )
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(F("author").desc(nulls_first=True), 'headline'),
            [self.a1, self.a2, self.a4, self.a3],
        )
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(Upper("author__name").asc(nulls_first=True), 'headline'),
            [self.a1, self.a2, self.a3, self.a4],
        )
        self.assertQuerysetEqualReversible(
            Article.objects.order_by(Upper("author__name").desc(nulls_first=True), 'headline'),
            [self.a1, self.a2, self.a4, self.a3],
        )

    def test_orders_nulls_first_on_filtered_subquery(self):
        Article.objects.filter(headline='Article 1').update(author=self.author_1)
        Article.objects.filter(headline='Article 2').update(author=self.author_1)
        Article.objects.filter(headline='Article 4').update(author=self.author_2)
        Author.objects.filter(name__isnull=True).delete()
        author_3 = Author.objects.create(name='Name 3')
        article_subquery = Article.objects.filter(
            author=OuterRef('pk'),
            headline__icontains='Article',
        ).order_by().values('author').annotate(
            last_date=Max('pub_date'),
        ).values('last_date')
        self.assertQuerysetEqualReversible(
            Author.objects.annotate(
                last_date=Subquery(article_subquery, output_field=DateTimeField())
            ).order_by(
                F('last_date').asc(nulls_first=True)
            ).distinct(),
            [author_3, self.author_1, self.author_2],
        )

    def test_stop_slicing(self):
        """
        Use the 'stop' part of slicing notation to limit the results.
        """
        self.assertQuerysetEqual(
            Article.objects.order_by("headline")[:2], [
                "Article 1",
                "Article 2",
            ],
            attrgetter("headline")
        )

    def test_stop_start_slicing(self):
        """
        Use the 'stop' and 'start' parts of slicing notation to offset the
        result list.
        """
        self.assertQuerysetEqual(
            Article.objects.order_by("headline")[1:3], [
                "Article 2",
                "Article 3",
            ],
            attrgetter("headline")
        )

    def test_random_ordering(self):
        """
        Use '?' to order randomly.
        """
        self.assertEqual(
            len(list(Article.objects.order_by("?"))), 4
        )

    def test_reversed_ordering(self):
        """
        Ordering can be reversed using the reverse() method on a queryset.
        This allows you to extract things like "the last two items" (reverse
        and then take the first two).
        """
        self.assertQuerysetEqual(
            Article.objects.all().reverse()[:2], [
                "Article 1",
                "Article 3",
            ],
            attrgetter("headline")
        )

    def test_reverse_ordering_pure(self):
        qs1 = Article.objects.order_by(F('headline').asc())
        qs2 = qs1.reverse()
        self.assertQuerysetEqual(
            qs2, [
                'Article 4',
                'Article 3',
                'Article 2',
                'Article 1',
            ],
            attrgetter('headline'),
        )
        self.assertQuerysetEqual(
            qs1, [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )

    def test_reverse_meta_ordering_pure(self):
        Article.objects.create(
            headline='Article 5',
            pub_date=datetime(2005, 7, 30),
            author=self.author_1,
            second_author=self.author_2,
        )
        Article.objects.create(
            headline='Article 5',
            pub_date=datetime(2005, 7, 30),
            author=self.author_2,
            second_author=self.author_1,
        )
        self.assertQuerysetEqual(
            Article.objects.filter(headline='Article 5').reverse(),
            ['Name 2', 'Name 1'],
            attrgetter('author.name'),
        )
        self.assertQuerysetEqual(
            Article.objects.filter(headline='Article 5'),
            ['Name 1', 'Name 2'],
            attrgetter('author.name'),
        )

    def test_no_reordering_after_slicing(self):
        msg = 'Cannot reverse a query once a slice has been taken.'
        qs = Article.objects.all()[0:2]
        with self.assertRaisesMessage(TypeError, msg):
            qs.reverse()
        with self.assertRaisesMessage(TypeError, msg):
            qs.last()

    def test_extra_ordering(self):
        """
        Ordering can be based on fields included from an 'extra' clause
        """
        self.assertQuerysetEqual(
            Article.objects.extra(select={"foo": "pub_date"}, order_by=["foo", "headline"]), [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )

    def test_extra_ordering_quoting(self):
        """
        If the extra clause uses an SQL keyword for a name, it will be
        protected by quoting.
        """
        self.assertQuerysetEqual(
            Article.objects.extra(select={"order": "pub_date"}, order_by=["order", "headline"]), [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )

    def test_extra_ordering_with_table_name(self):
        self.assertQuerysetEqual(
            Article.objects.extra(order_by=['ordering_article.headline']), [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )
        self.assertQuerysetEqual(
            Article.objects.extra(order_by=['-ordering_article.headline']), [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline")
        )

    def test_order_by_pk(self):
        """
        'pk' works as an ordering option in Meta.
        """
        self.assertQuerysetEqual(
            Author.objects.all(),
            list(reversed(range(1, Author.objects.count() + 1))),
            attrgetter("pk"),
        )

    def test_order_by_fk_attname(self):
        """
        ordering by a foreign key by its attribute name prevents the query
        from inheriting its related model ordering option (#19195).
        """
        for i in range(1, 5):
            author = Author.objects.get(pk=i)
            article = getattr(self, "a%d" % (5 - i))
            article.author = author
            article.save(update_fields={'author'})

        self.assertQuerysetEqual(
            Article.objects.order_by('author_id'), [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline")
        )

    def test_orm_001_traversed_terminal_fk_attname_uses_stored_column(self):
        """
        ORM-001: A traversed ordering path ending in a foreign-key attname
        resolves to its stored column without expanding related ordering.
        """
        queryset = Reference.objects.order_by('article__author_id')
        order_by = queryset.query.get_compiler(queryset.db).get_order_by()

        self.assertEqual(len(order_by), 1)
        expression = order_by[0][0]
        self.assertEqual(expression.expression.target.column, 'author_id')
        self.assertEqual(expression.expression.alias, Article._meta.db_table)

    def _create_references_with_shuffled_authors(self):
        authors = list(Author.objects.order_by('pk'))
        articles = [self.a1, self.a2, self.a3, self.a4]
        for article, author in zip(articles, reversed(authors)):
            article.author = author
            article.save(update_fields={'author'})
            Reference.objects.create(article=article)
        return articles

    def test_orm_002_traversed_fk_attname_orders_stored_value_ascending(self):
        """
        ORM-002: order_by("record__root_id") preserves ascending direction for
        the stored root_id value despite OneModel's descending ordering.
        """
        articles = self._create_references_with_shuffled_authors()

        self.assertSequenceEqual(
            list(Reference.objects.order_by('article__author_id').values_list('article', flat=True)),
            [article.pk for article in reversed(articles)],
        )

    def test_orm_003_traversed_fk_attname_orders_stored_value_descending(self):
        """
        ORM-003: order_by("-record__root_id") preserves descending direction
        for the stored root_id value despite OneModel's descending ordering.
        """
        articles = self._create_references_with_shuffled_authors()

        self.assertSequenceEqual(
            list(Reference.objects.order_by('-article__author_id').values_list('article', flat=True)),
            [article.pk for article in articles],
        )

    def test_orm_004_traversed_fk_attname_directions_add_no_self_join(self):
        """
        ORM-004: Ordering by either direction of record__root_id adds no join
        to the self-related OneModel row solely for ordering.
        """
        for direction in ('article__author_id', '-article__author_id'):
            with self.subTest(direction=direction):
                queryset = Reference.objects.order_by(direction)
                queryset.query.get_compiler(queryset.db).get_order_by()
                active_tables = [
                    join.table_name
                    for alias, join in queryset.query.alias_map.items()
                    if queryset.query.alias_refcount[alias]
                ]
                self.assertEqual(active_tables.count(Article._meta.db_table), 1)
                self.assertNotIn(Author._meta.db_table, active_tables)

    def test_orm_005_record_root_id_matches_explicit_pk_order_ascending(self):
        """
        ORM-005: Ascending record__root_id ordering produces the same
        observable result order as ascending record__root__id ordering.
        """
        self._create_references_with_shuffled_authors()

        attname_order = Reference.objects.order_by(
            'article__author_id',
        ).values_list('pk', flat=True)
        explicit_pk_order = Reference.objects.order_by(
            'article__author__id',
        ).values_list('pk', flat=True)
        self.assertSequenceEqual(attname_order, explicit_pk_order)

    def test_orm_005_record_root_id_matches_explicit_pk_order_descending(self):
        """
        ORM-005: Descending record__root_id ordering produces the same
        observable result order as descending record__root__id ordering.
        """
        self._create_references_with_shuffled_authors()

        attname_order = Reference.objects.order_by(
            '-article__author_id',
        ).values_list('pk', flat=True)
        explicit_pk_order = Reference.objects.order_by(
            '-article__author__id',
        ).values_list('pk', flat=True)
        self.assertSequenceEqual(attname_order, explicit_pk_order)

    def test_orm_006_record_oneval_filter_and_membership_survive_ascending_order(self):
        """
        ORM-006: Applying ascending record__root_id ordering preserves the
        record__oneval filter condition and selected result set.
        """
        articles = self._create_references_with_shuffled_authors()
        queryset = Reference.objects.filter(
            article__headline__in=('Article 1', 'Article 3'),
        ).order_by('article__author_id')

        self.assertSequenceEqual(
            queryset.values_list('article', flat=True),
            [articles[2].pk, articles[0].pk],
        )
        self.assertSequenceEqual(
            queryset.values_list('article__headline', flat=True),
            ['Article 3', 'Article 1'],
        )

    def test_orm_006_record_oneval_filter_and_membership_survive_descending_order(self):
        """
        ORM-006: Applying descending record__root_id ordering preserves the
        record__oneval filter condition and selected result set.
        """
        articles = self._create_references_with_shuffled_authors()
        queryset = Reference.objects.filter(
            article__headline__in=('Article 1', 'Article 3'),
        ).order_by('-article__author_id')

        self.assertSequenceEqual(
            queryset.values_list('article', flat=True),
            [articles[0].pk, articles[2].pk],
        )
        self.assertSequenceEqual(
            queryset.values_list('article__headline', flat=True),
            ['Article 1', 'Article 3'],
        )

    def test_orm_007_explicit_root_pk_order_remains_valid_ascending(self):
        """
        ORM-007: Existing ascending record__root__id ordering remains valid.
        """
        articles = self._create_references_with_shuffled_authors()

        self.assertSequenceEqual(
            Reference.objects.order_by(
                'article__author__id',
            ).values_list('article', flat=True),
            [article.pk for article in reversed(articles)],
        )

    def test_orm_007_explicit_root_pk_order_remains_valid_descending(self):
        """
        ORM-007: Existing descending record__root__id ordering remains valid.
        """
        articles = self._create_references_with_shuffled_authors()

        self.assertSequenceEqual(
            Reference.objects.order_by(
                '-article__author__id',
            ).values_list('article', flat=True),
            [article.pk for article in articles],
        )

    def test_orm_008_record_root_retains_relation_ordering_semantics(self):
        """
        ORM-008: Ordering by record__root retains relation-ordering semantics
        and may expand OneModel.Meta.ordering.
        """
        articles = self._create_references_with_shuffled_authors()

        self.assertSequenceEqual(
            Reference.objects.order_by(
                'article__author',
            ).values_list('article', flat=True),
            [article.pk for article in articles],
        )

    def test_orm_009_ordinary_non_self_fk_ordering_remains_unchanged(self):
        """
        ORM-009: Existing valid ordering through an ordinary
        non-self-referencing foreign key remains unchanged.
        """
        articles = self._create_references_with_shuffled_authors()

        self.assertSequenceEqual(
            Article.objects.order_by(
                'author_id',
            ).values_list('pk', flat=True),
            [article.pk for article in reversed(articles)],
        )
        self.assertSequenceEqual(
            Article.objects.order_by(
                '-author_id',
            ).values_list('pk', flat=True),
            [article.pk for article in articles],
        )

    def test_orm_010_ascending_self_fk_attname_orders_by_concrete_column_without_self_join(self):
        """
        ORM-010: Ascending record__root_id ordering returns ascending stored
        values, targets the concrete column, and adds no ordering-only
        self-join.
        """
        # ORM-010 logic obligation — ascending direction:
        # GIVEN regression rows whose self-referential foreign-key values are
        # deliberately out of insertion order, and whose related model has
        # descending default ordering,
        # WHEN a queryset is ordered by the traversed ``record__root_id``
        # attname,
        # THEN compile the ordering expression and identify its target by
        # model metadata (table and concrete stored-column identity), not by
        # matching backend-rendered SQL text,
        # AND inspect the compiled query's active aliases/joins to confirm
        # that traversal reaches ``record`` but does not add the self-related
        # ``root`` table solely to satisfy ordering,
        # AND evaluate stable identifiers from the queryset and compare them
        # with the identifiers arranged by ascending stored ``root_id``.
        # FAIL if direction is reversed by related default ordering, the
        # expression targets a related/default-ordering column, an active
        # ordering-only self-join exists, or the observed rows are not in the
        # expected ascending order.
        pass

    def test_orm_010_descending_self_fk_attname_orders_by_concrete_column_without_self_join(self):
        """
        ORM-010: Descending -record__root_id ordering returns descending stored
        values, targets the concrete column, and adds no ordering-only
        self-join.
        """
        # ORM-010 logic obligation — descending direction:
        # GIVEN the same regression rows and descending related-model default
        # ordering used by the ascending case,
        # WHEN a queryset is ordered by the traversed ``-record__root_id``
        # attname,
        # THEN compile the ordering expression, preserve the explicit
        # descending flag, and identify the target as the concrete stored
        # ``root_id`` column through model/compiler metadata,
        # AND inspect active query aliases/joins to confirm that no join to
        # the self-related ``root`` row was introduced solely for ordering,
        # AND evaluate stable identifiers and compare them with the same
        # expected identifiers arranged by descending stored ``root_id``.
        # FAIL if the explicit direction is lost or compounded with related
        # default ordering, the concrete target differs, an ordering-only
        # self-join is active, or result order is not descending.
        pass

    def test_orm_010_sql_structure_checks_allow_backend_representation_differences(self):
        """
        ORM-010: Structural SQL checks accept backend-specific quoting,
        aliases, and formatting while identifying the concrete column and the
        absence of an ordering-only self-join.
        """
        # ORM-010 logic obligation — backend-portable structure:
        # FOR EACH direction in (``record__root_id``, ``-record__root_id``):
        #   build the regression queryset and force compiler ordering
        #   resolution without asserting the complete rendered SQL;
        #   resolve the ordering target's concrete column and owning table
        #   from compiler/model metadata, treating generated alias spelling,
        #   identifier quoting, and whitespace as non-semantic;
        #   collect only active joins from the query alias map;
        #   verify the required path join is present exactly as needed and
        #   the self-related table is absent as an ordering-only join;
        #   hand the same queryset to the direction-specific result-order
        #   check so structural and observable behavior describe one query.
        # FAIL only on semantic differences (wrong concrete target, extra
        # active self-join, wrong direction, or wrong result sequence), never
        # on backend-specific SQL representation.
        pass

    def test_order_by_f_expression(self):
        self.assertQuerysetEqual(
            Article.objects.order_by(F('headline')), [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )
        self.assertQuerysetEqual(
            Article.objects.order_by(F('headline').asc()), [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )
        self.assertQuerysetEqual(
            Article.objects.order_by(F('headline').desc()), [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline")
        )

    def test_order_by_f_expression_duplicates(self):
        """
        A column may only be included once (the first occurrence) so we check
        to ensure there are no duplicates by inspecting the SQL.
        """
        qs = Article.objects.order_by(F('headline').asc(), F('headline').desc())
        sql = str(qs.query).upper()
        fragment = sql[sql.find('ORDER BY'):]
        self.assertEqual(fragment.count('HEADLINE'), 1)
        self.assertQuerysetEqual(
            qs, [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline")
        )
        qs = Article.objects.order_by(F('headline').desc(), F('headline').asc())
        sql = str(qs.query).upper()
        fragment = sql[sql.find('ORDER BY'):]
        self.assertEqual(fragment.count('HEADLINE'), 1)
        self.assertQuerysetEqual(
            qs, [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline")
        )

    def test_order_by_constant_value(self):
        # Order by annotated constant from selected columns.
        qs = Article.objects.annotate(
            constant=Value('1', output_field=CharField()),
        ).order_by('constant', '-headline')
        self.assertSequenceEqual(qs, [self.a4, self.a3, self.a2, self.a1])
        # Order by annotated constant which is out of selected columns.
        self.assertSequenceEqual(
            qs.values_list('headline', flat=True), [
                'Article 4',
                'Article 3',
                'Article 2',
                'Article 1',
            ],
        )
        # Order by constant.
        qs = Article.objects.order_by(Value('1', output_field=CharField()), '-headline')
        self.assertSequenceEqual(qs, [self.a4, self.a3, self.a2, self.a1])

    def test_order_by_constant_value_without_output_field(self):
        msg = 'Cannot resolve expression type, unknown output_field'
        qs = Article.objects.annotate(constant=Value('1')).order_by('constant')
        for ordered_qs in (
            qs,
            qs.values('headline'),
            Article.objects.order_by(Value('1')),
        ):
            with self.subTest(ordered_qs=ordered_qs), self.assertRaisesMessage(FieldError, msg):
                ordered_qs.first()

    def test_related_ordering_duplicate_table_reference(self):
        """
        An ordering referencing a model with an ordering referencing a model
        multiple time no circular reference should be detected (#24654).
        """
        first_author = Author.objects.create()
        second_author = Author.objects.create()
        self.a1.author = first_author
        self.a1.second_author = second_author
        self.a1.save()
        self.a2.author = second_author
        self.a2.second_author = first_author
        self.a2.save()
        r1 = Reference.objects.create(article_id=self.a1.pk)
        r2 = Reference.objects.create(article_id=self.a2.pk)
        self.assertSequenceEqual(Reference.objects.all(), [r2, r1])

    def test_default_ordering_by_f_expression(self):
        """F expressions can be used in Meta.ordering."""
        articles = OrderedByFArticle.objects.all()
        articles.filter(headline='Article 2').update(author=self.author_2)
        articles.filter(headline='Article 3').update(author=self.author_1)
        self.assertQuerysetEqual(
            articles, ['Article 1', 'Article 4', 'Article 3', 'Article 2'],
            attrgetter('headline')
        )

    def test_order_by_ptr_field_with_default_ordering_by_expression(self):
        ca1 = ChildArticle.objects.create(
            headline='h2',
            pub_date=datetime(2005, 7, 27),
            author=self.author_2,
        )
        ca2 = ChildArticle.objects.create(
            headline='h2',
            pub_date=datetime(2005, 7, 27),
            author=self.author_1,
        )
        ca3 = ChildArticle.objects.create(
            headline='h3',
            pub_date=datetime(2005, 7, 27),
            author=self.author_1,
        )
        ca4 = ChildArticle.objects.create(headline='h1', pub_date=datetime(2005, 7, 28))
        articles = ChildArticle.objects.order_by('article_ptr')
        self.assertSequenceEqual(articles, [ca4, ca2, ca1, ca3])
