from django.db.models import FilteredRelation
from django.test import TestCase

from .models import Organiser, Pool, PoolStyle, Tournament


class MultiLevelFilteredRelationAssignmentContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tournament = Tournament.objects.create(name="Tourney")
        cls.other_tournament = Tournament.objects.create(name="Other Tourney")
        organiser = Organiser.objects.create(name="Organiser")
        cls.pool = Pool.objects.create(
            name="Pool", tournament=cls.tournament, organiser=organiser
        )
        cls.tournament_pool = Pool.objects.create(
            name="Tournament Pool", tournament=cls.tournament, organiser=organiser
        )
        other_pool = Pool.objects.create(
            name="Other Pool", tournament=cls.other_tournament, organiser=organiser
        )
        cls.style = PoolStyle.objects.create(name="Style", pool=cls.pool)
        PoolStyle.objects.create(name="Other Style", pool=other_pool)

    def get_results(self):
        return list(
            PoolStyle.objects.annotate(
                tournament_pool=FilteredRelation("pool__tournament__pool"),
            )
            .select_related("tournament_pool", "tournament_pool__tournament")
            .order_by("pk", "tournament_pool__pk")
        )

    def test_DJFR_001_evaluation_assigns_terminal_pool_to_tournament_pool(self):
        """GUID: DJFR-001 - Evaluation assigns the terminal Pool."""
        results = self.get_results()

        self.assertTrue(results)
        for style in results:
            self.assertIsInstance(style.tournament_pool, Pool)
            self.assertEqual(
                style.tournament_pool.tournament_id, style.pool.tournament_id
            )

    def test_DJFR_002_traversal_returns_tournaments_at_both_paths(self):
        """GUID: DJFR-002 - Both traversed paths return Tournament objects."""
        for style in self.get_results():
            self.assertIsInstance(style.pool.tournament, Tournament)
            self.assertIsInstance(style.tournament_pool.tournament, Tournament)

    def test_DJFR_003_traversed_tournaments_represent_same_equal_value(self):
        """GUID: DJFR-003 - Both paths reach the same, equal tournament."""
        for style in self.get_results():
            self.assertEqual(style.pool.tournament, style.tournament_pool.tournament)

    def test_DJFR_004_reused_object_matches_model_and_relationship_level(self):
        """GUID: DJFR-004 - Reuse preserves the expected model and path level."""
        for style in self.get_results():
            self.assertIsInstance(style, PoolStyle)
            self.assertIsInstance(style.pool, Pool)
            self.assertIsInstance(style.tournament_pool, Pool)
            self.assertIsInstance(style.pool.tournament, Tournament)
            self.assertIsInstance(style.tournament_pool.tournament, Tournament)

    def test_DJFR_005_annotation_preserves_pool_and_tournament_semantics(self):
        """GUID: DJFR-005 - Annotation preserves the underlying relationships."""
        expected_pool_ids = {
            style.pk: style.pool_id for style in PoolStyle.objects.all()
        }
        expected_tournament_ids = {
            pool.pk: pool.tournament_id for pool in Pool.objects.all()
        }

        for style in self.get_results():
            self.assertEqual(style.pool_id, expected_pool_ids[style.pk])
            self.assertEqual(
                style.pool.tournament_id, expected_tournament_ids[style.pool_id]
            )

    def test_DJFR_006_evaluation_and_traversal_execute_three_queries(self):
        """GUID: DJFR-006 - Evaluation and traversal execute three queries."""
        with self.assertNumQueries(3):
            results = self.get_results()
            pool_tournament = results[0].pool.tournament
            tournament_pool_tournament = results[0].tournament_pool.tournament
            self.assertEqual(pool_tournament, tournament_pool_tournament)

    def test_DJFR_007_existing_related_filtered_select_related_is_unchanged(self):
        """GUID: DJFR-007 - Existing related-query behavior remains unchanged."""
        with self.assertNumQueries(1):
            style = (
                PoolStyle.objects.annotate(pool_alias=FilteredRelation("pool"))
                .select_related("pool_alias")
                .get(pk=self.style.pk)
            )
            self.assertEqual(style.pool_alias, self.pool)
            self.assertIs(style, style.pool_alias.poolstyle)


class ExistingRelatedInstancesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.t1 = Tournament.objects.create(name="Tourney 1")
        cls.t2 = Tournament.objects.create(name="Tourney 2")
        cls.o1 = Organiser.objects.create(name="Organiser 1")
        cls.p1 = Pool.objects.create(
            name="T1 Pool 1", tournament=cls.t1, organiser=cls.o1
        )
        cls.p2 = Pool.objects.create(
            name="T1 Pool 2", tournament=cls.t1, organiser=cls.o1
        )
        cls.p3 = Pool.objects.create(
            name="T2 Pool 1", tournament=cls.t2, organiser=cls.o1
        )
        cls.p4 = Pool.objects.create(
            name="T2 Pool 2", tournament=cls.t2, organiser=cls.o1
        )
        cls.ps1 = PoolStyle.objects.create(name="T1 Pool 2 Style", pool=cls.p2)
        cls.ps2 = PoolStyle.objects.create(name="T2 Pool 1 Style", pool=cls.p3)
        cls.ps3 = PoolStyle.objects.create(
            name="T1 Pool 1/3 Style", pool=cls.p1, another_pool=cls.p3
        )

    def test_foreign_key(self):
        with self.assertNumQueries(2):
            tournament = Tournament.objects.get(pk=self.t1.pk)
            pool = tournament.pool_set.all()[0]
            self.assertIs(tournament, pool.tournament)

    def test_foreign_key_prefetch_related(self):
        with self.assertNumQueries(2):
            tournament = Tournament.objects.prefetch_related("pool_set").get(
                pk=self.t1.pk
            )
            pool = tournament.pool_set.all()[0]
            self.assertIs(tournament, pool.tournament)

    def test_foreign_key_multiple_prefetch(self):
        with self.assertNumQueries(2):
            tournaments = list(
                Tournament.objects.prefetch_related("pool_set").order_by("pk")
            )
            pool1 = tournaments[0].pool_set.all()[0]
            self.assertIs(tournaments[0], pool1.tournament)
            pool2 = tournaments[1].pool_set.all()[0]
            self.assertIs(tournaments[1], pool2.tournament)

    def test_queryset_or(self):
        tournament_1 = self.t1
        tournament_2 = self.t2
        with self.assertNumQueries(1):
            pools = tournament_1.pool_set.all() | tournament_2.pool_set.all()
            related_objects = {pool.tournament for pool in pools}
            self.assertEqual(related_objects, {tournament_1, tournament_2})

    def test_queryset_or_different_cached_items(self):
        tournament = self.t1
        organiser = self.o1
        with self.assertNumQueries(1):
            pools = tournament.pool_set.all() | organiser.pool_set.all()
            first = pools.filter(pk=self.p1.pk)[0]
            self.assertIs(first.tournament, tournament)
            self.assertIs(first.organiser, organiser)

    def test_queryset_or_only_one_with_precache(self):
        tournament_1 = self.t1
        tournament_2 = self.t2
        # 2 queries here as pool 3 has tournament 2, which is not cached
        with self.assertNumQueries(2):
            pools = tournament_1.pool_set.all() | Pool.objects.filter(pk=self.p3.pk)
            related_objects = {pool.tournament for pool in pools}
            self.assertEqual(related_objects, {tournament_1, tournament_2})
        # and the other direction
        with self.assertNumQueries(2):
            pools = Pool.objects.filter(pk=self.p3.pk) | tournament_1.pool_set.all()
            related_objects = {pool.tournament for pool in pools}
            self.assertEqual(related_objects, {tournament_1, tournament_2})

    def test_queryset_and(self):
        tournament = self.t1
        organiser = self.o1
        with self.assertNumQueries(1):
            pools = tournament.pool_set.all() & organiser.pool_set.all()
            first = pools.filter(pk=self.p1.pk)[0]
            self.assertIs(first.tournament, tournament)
            self.assertIs(first.organiser, organiser)

    def test_one_to_one(self):
        with self.assertNumQueries(2):
            style = PoolStyle.objects.get(pk=self.ps1.pk)
            pool = style.pool
            self.assertIs(style, pool.poolstyle)

    def test_one_to_one_select_related(self):
        with self.assertNumQueries(1):
            style = PoolStyle.objects.select_related("pool").get(pk=self.ps1.pk)
            pool = style.pool
            self.assertIs(style, pool.poolstyle)

    def test_one_to_one_multi_select_related(self):
        with self.assertNumQueries(1):
            poolstyles = list(PoolStyle.objects.select_related("pool").order_by("pk"))
            self.assertIs(poolstyles[0], poolstyles[0].pool.poolstyle)
            self.assertIs(poolstyles[1], poolstyles[1].pool.poolstyle)

    def test_one_to_one_prefetch_related(self):
        with self.assertNumQueries(2):
            style = PoolStyle.objects.prefetch_related("pool").get(pk=self.ps1.pk)
            pool = style.pool
            self.assertIs(style, pool.poolstyle)

    def test_one_to_one_multi_prefetch_related(self):
        with self.assertNumQueries(2):
            poolstyles = list(PoolStyle.objects.prefetch_related("pool").order_by("pk"))
            self.assertIs(poolstyles[0], poolstyles[0].pool.poolstyle)
            self.assertIs(poolstyles[1], poolstyles[1].pool.poolstyle)

    def test_reverse_one_to_one(self):
        with self.assertNumQueries(2):
            pool = Pool.objects.get(pk=self.p2.pk)
            style = pool.poolstyle
            self.assertIs(pool, style.pool)

    def test_reverse_one_to_one_select_related(self):
        with self.assertNumQueries(1):
            pool = Pool.objects.select_related("poolstyle").get(pk=self.p2.pk)
            style = pool.poolstyle
            self.assertIs(pool, style.pool)

    def test_reverse_one_to_one_prefetch_related(self):
        with self.assertNumQueries(2):
            pool = Pool.objects.prefetch_related("poolstyle").get(pk=self.p2.pk)
            style = pool.poolstyle
            self.assertIs(pool, style.pool)

    def test_reverse_one_to_one_multi_select_related(self):
        with self.assertNumQueries(1):
            pools = list(Pool.objects.select_related("poolstyle").order_by("pk"))
            self.assertIs(pools[1], pools[1].poolstyle.pool)
            self.assertIs(pools[2], pools[2].poolstyle.pool)

    def test_reverse_one_to_one_multi_prefetch_related(self):
        with self.assertNumQueries(2):
            pools = list(Pool.objects.prefetch_related("poolstyle").order_by("pk"))
            self.assertIs(pools[1], pools[1].poolstyle.pool)
            self.assertIs(pools[2], pools[2].poolstyle.pool)

    def test_reverse_fk_select_related_multiple(self):
        with self.assertNumQueries(1):
            ps = list(
                PoolStyle.objects.annotate(
                    pool_1=FilteredRelation("pool"),
                    pool_2=FilteredRelation("another_pool"),
                )
                .select_related("pool_1", "pool_2")
                .order_by("-pk")
            )
            self.assertIs(ps[0], ps[0].pool_1.poolstyle)
            self.assertIs(ps[0], ps[0].pool_2.another_style)
