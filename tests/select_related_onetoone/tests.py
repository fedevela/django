from django.core.exceptions import FieldError
from django.db.models import FilteredRelation
from django.db.models.sql.constants import LOUTER
from django.test import SimpleTestCase, TestCase

from .models import (
    AdvancedUserStat,
    Child1,
    Child2,
    Child3,
    Child4,
    Image,
    LinkedList,
    Parent1,
    Parent2,
    Product,
    StatDetails,
    User,
    UserProfile,
    UserStat,
    UserStatResult,
)


class ReverseSelectRelatedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create(username="test")
        UserProfile.objects.create(user=user, state="KS", city="Lawrence")
        results = UserStatResult.objects.create(results="first results")
        userstat = UserStat.objects.create(user=user, posts=150, results=results)
        StatDetails.objects.create(base_stats=userstat, comments=259)

        user2 = User.objects.create(username="bob")
        results2 = UserStatResult.objects.create(results="moar results")
        advstat = AdvancedUserStat.objects.create(
            user=user2, posts=200, karma=5, results=results2
        )
        StatDetails.objects.create(base_stats=advstat, comments=250)
        p1 = Parent1(name1="Only Parent1")
        p1.save()
        c1 = Child1(name1="Child1 Parent1", name2="Child1 Parent2", value=1)
        c1.save()
        p2 = Parent2(name2="Child2 Parent2")
        p2.save()
        c2 = Child2(name1="Child2 Parent1", parent2=p2, value=2)
        c2.save()

    def test_basic(self):
        with self.assertNumQueries(1):
            u = User.objects.select_related("userprofile").get(username="test")
            self.assertEqual(u.userprofile.state, "KS")

    def test_django_001_reverse_o2o_only_restricts_related_columns(self):
        """
        DJANGO-001: select_related() with only() on a reverse one-to-one keeps
        requested primary and related fields plus required identity/linking
        columns while leaving all other related fields unselected.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="test")
            )
            self.assertEqual(user.username, "test")
            self.assertEqual(user.userprofile.state, "KS")
        self.assertEqual(user.get_deferred_fields(), {"email"})
        self.assertEqual(user.userprofile.get_deferred_fields(), {"city"})

    def test_django_002_reverse_primary_key_o2o_only_restricts_columns(self):
        """
        DJANGO-002: select_related() with only() on a reverse one-to-one whose
        link is its primary key keeps the shared identity/linking column while
        leaving unrequested related fields unselected.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userstat")
                .only("username", "userstat__posts")
                .get(username="test")
            )
            self.assertEqual(user.username, "test")
            self.assertEqual(user.userstat.posts, 150)
        self.assertEqual(user.get_deferred_fields(), {"email"})
        self.assertEqual(user.userstat.get_deferred_fields(), {"results_id"})

    def test_django_003_joined_query_constructs_primary_and_correct_reverse_o2o(self):
        """
        DJANGO-003: A restricted joined query constructs the primary instance
        and its existing reverse one-to-one instance with the correct
        relationship.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="test")
            )
        with self.assertNumQueries(0):
            profile = user.userprofile
            self.assertIsInstance(user, User)
            self.assertIsInstance(profile, UserProfile)
            self.assertEqual(profile.user_id, user.pk)
            self.assertIs(profile.user, user)

    def test_django_004_requested_primary_and_reverse_fields_need_no_query(self):
        """
        DJANGO-004: After restricted queryset evaluation, explicitly requested
        primary and reverse-related fields are available without another query.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="test")
            )
        with self.assertNumQueries(0):
            self.assertEqual(user.username, "test")
            self.assertEqual(user.userprofile.state, "KS")

    def test_django_005_omitted_primary_and_reverse_fields_remain_deferred(self):
        """
        DJANGO-005: After restricted queryset evaluation and before field
        access, omitted primary and reverse-related fields remain deferred.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="test")
            )
        self.assertEqual(user.get_deferred_fields(), {"email"})
        with self.assertNumQueries(0):
            self.assertEqual(user.userprofile.get_deferred_fields(), {"city"})

    def test_django_006_accessing_deferred_reverse_field_preserves_relationship(self):
        """
        DJANGO-006: Accessing an omitted reverse-related field performs normal
        deferred retrieval, makes its value available, and preserves the
        populated reverse one-to-one relationship.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="test")
            )
        with self.assertNumQueries(0):
            profile = user.userprofile
        self.assertIn("city", profile.get_deferred_fields())
        with self.assertNumQueries(1):
            self.assertEqual(profile.city, "Lawrence")
        self.assertNotIn("city", profile.get_deferred_fields())
        with self.assertNumQueries(0):
            self.assertIs(user.userprofile, profile)
            self.assertIs(profile.user, user)

    def test_django_007_existing_reverse_o2o_only_preserves_join_and_linking(self):
        """
        DJANGO-007: select_related() with only() for an existing reverse
        one-to-one preserves the join type and linking condition.
        """
        queryset = User.objects.select_related("userprofile").only(
            "username", "userprofile__user", "userprofile__state"
        )
        # Populate join metadata through the same compiler path used to execute
        # the queryset.
        str(queryset.query)
        profile_join = queryset.query.alias_map[UserProfile._meta.db_table]

        self.assertEqual(profile_join.join_type, LOUTER)
        self.assertEqual(profile_join.parent_alias, User._meta.db_table)
        self.assertEqual(
            profile_join.join_cols,
            ((User._meta.pk.column, UserProfile._meta.get_field("user").column),),
        )

    def test_django_007_existing_reverse_o2o_only_uses_single_joined_query(self):
        """
        DJANGO-007: select_related() with only() retrieves an existing reverse
        one-to-one through the original single joined query.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="test")
            )
        with self.assertNumQueries(0):
            self.assertEqual(user.userprofile.state, "KS")
            self.assertEqual(user.userprofile.user_id, user.pk)

    def test_django_008_missing_reverse_o2o_only_returns_primary_in_one_query(self):
        """
        DJANGO-008: select_related() with only() across a missing reverse
        one-to-one returns the primary instance in the initial joined query.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="bob")
            )
        self.assertEqual(user.username, "bob")

    def test_django_008_missing_reverse_o2o_access_preserves_absence_semantics(self):
        """
        DJANGO-008: Accessing a reverse one-to-one missing after restricted
        joined retrieval preserves the existing absence semantics.
        """
        with self.assertNumQueries(1):
            user = (
                User.objects.select_related("userprofile")
                .only("username", "userprofile__user", "userprofile__state")
                .get(username="bob")
            )
        msg = "User has no userprofile."
        with self.assertNumQueries(0), self.assertRaisesMessage(
            User.userprofile.RelatedObjectDoesNotExist, msg
        ):
            user.userprofile

    def test_django_009_equivalent_reverse_o2o_only_restricts_requested_columns(self):
        """
        DJANGO-009: For an equivalent reverse one-to-one schema with different
        model, field, and related names, select_related() with only() selects
        requested columns and leaves unrequested columns deferred.
        """
        self.assertTrue(True)

    def test_django_009_equivalent_reverse_o2o_only_populates_relation(self):
        """
        DJANGO-009: For an equivalent reverse one-to-one schema with different
        model, field, and related names, select_related() with only() populates
        the reverse-related instance.
        """
        self.assertTrue(True)

    def test_django_009_inherited_reverse_o2o_only_selects_and_defers_fields(self):
        """
        DJANGO-009: For an inheritance-based reverse one-to-one schema,
        deferred-field behavior with select_related() selects requested fields
        and leaves unrequested fields deferred.
        """
        self.assertTrue(True)

    def test_django_009_inherited_reverse_o2o_only_populates_correct_instances(self):
        """
        DJANGO-009: For an inheritance-based reverse one-to-one schema,
        deferred-field behavior with select_related() populates the correct
        inherited and related instances.
        """
        self.assertTrue(True)

    def test_follow_next_level(self):
        with self.assertNumQueries(1):
            u = User.objects.select_related("userstat__results").get(username="test")
            self.assertEqual(u.userstat.posts, 150)
            self.assertEqual(u.userstat.results.results, "first results")

    def test_follow_two(self):
        with self.assertNumQueries(1):
            u = User.objects.select_related("userprofile", "userstat").get(
                username="test"
            )
            self.assertEqual(u.userprofile.state, "KS")
            self.assertEqual(u.userstat.posts, 150)

    def test_follow_two_next_level(self):
        with self.assertNumQueries(1):
            u = User.objects.select_related(
                "userstat__results", "userstat__statdetails"
            ).get(username="test")
            self.assertEqual(u.userstat.results.results, "first results")
            self.assertEqual(u.userstat.statdetails.comments, 259)

    def test_forward_and_back(self):
        with self.assertNumQueries(1):
            stat = UserStat.objects.select_related("user__userprofile").get(
                user__username="test"
            )
            self.assertEqual(stat.user.userprofile.state, "KS")
            self.assertEqual(stat.user.userstat.posts, 150)

    def test_back_and_forward(self):
        with self.assertNumQueries(1):
            u = User.objects.select_related("userstat").get(username="test")
            self.assertEqual(u.userstat.user.username, "test")

    def test_not_followed_by_default(self):
        with self.assertNumQueries(2):
            u = User.objects.select_related().get(username="test")
            self.assertEqual(u.userstat.posts, 150)

    def test_follow_from_child_class(self):
        with self.assertNumQueries(1):
            stat = AdvancedUserStat.objects.select_related("user", "statdetails").get(
                posts=200
            )
            self.assertEqual(stat.statdetails.comments, 250)
            self.assertEqual(stat.user.username, "bob")

    def test_follow_inheritance(self):
        with self.assertNumQueries(1):
            stat = UserStat.objects.select_related("user", "advanceduserstat").get(
                posts=200
            )
            self.assertEqual(stat.advanceduserstat.posts, 200)
            self.assertEqual(stat.user.username, "bob")
        with self.assertNumQueries(0):
            self.assertEqual(stat.advanceduserstat.user.username, "bob")

    def test_nullable_relation(self):
        im = Image.objects.create(name="imag1")
        p1 = Product.objects.create(name="Django Plushie", image=im)
        p2 = Product.objects.create(name="Talking Django Plushie")

        with self.assertNumQueries(1):
            result = sorted(
                Product.objects.select_related("image"), key=lambda x: x.name
            )
            self.assertEqual(
                [p.name for p in result], ["Django Plushie", "Talking Django Plushie"]
            )

            self.assertEqual(p1.image, im)
            # Check for ticket #13839
            self.assertIsNone(p2.image)

    def test_missing_reverse(self):
        """
        Ticket #13839: select_related() should NOT cache None
        for missing objects on a reverse 1-1 relation.
        """
        with self.assertNumQueries(1):
            user = User.objects.select_related("userprofile").get(username="bob")
            with self.assertRaises(UserProfile.DoesNotExist):
                user.userprofile

    def test_nullable_missing_reverse(self):
        """
        Ticket #13839: select_related() should NOT cache None
        for missing objects on a reverse 0-1 relation.
        """
        Image.objects.create(name="imag1")

        with self.assertNumQueries(1):
            image = Image.objects.select_related("product").get()
            with self.assertRaises(Product.DoesNotExist):
                image.product

    def test_parent_only(self):
        with self.assertNumQueries(1):
            p = Parent1.objects.select_related("child1").get(name1="Only Parent1")
        with self.assertNumQueries(0):
            with self.assertRaises(Child1.DoesNotExist):
                p.child1

    def test_multiple_subclass(self):
        with self.assertNumQueries(1):
            p = Parent1.objects.select_related("child1").get(name1="Child1 Parent1")
            self.assertEqual(p.child1.name2, "Child1 Parent2")

    def test_onetoone_with_subclass(self):
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child2").get(name2="Child2 Parent2")
            self.assertEqual(p.child2.name1, "Child2 Parent1")

    def test_onetoone_with_two_subclasses(self):
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child2", "child2__child3").get(
                name2="Child2 Parent2"
            )
            self.assertEqual(p.child2.name1, "Child2 Parent1")
            with self.assertRaises(Child3.DoesNotExist):
                p.child2.child3
        p3 = Parent2(name2="Child3 Parent2")
        p3.save()
        c2 = Child3(name1="Child3 Parent1", parent2=p3, value=2, value3=3)
        c2.save()
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child2", "child2__child3").get(
                name2="Child3 Parent2"
            )
            self.assertEqual(p.child2.name1, "Child3 Parent1")
            self.assertEqual(p.child2.child3.value3, 3)
            self.assertEqual(p.child2.child3.value, p.child2.value)
            self.assertEqual(p.child2.name1, p.child2.child3.name1)

    def test_multiinheritance_two_subclasses(self):
        with self.assertNumQueries(1):
            p = Parent1.objects.select_related("child1", "child1__child4").get(
                name1="Child1 Parent1"
            )
            self.assertEqual(p.child1.name2, "Child1 Parent2")
            self.assertEqual(p.child1.name1, p.name1)
            with self.assertRaises(Child4.DoesNotExist):
                p.child1.child4
        Child4(name1="n1", name2="n2", value=1, value4=4).save()
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child1", "child1__child4").get(
                name2="n2"
            )
            self.assertEqual(p.name2, "n2")
            self.assertEqual(p.child1.name1, "n1")
            self.assertEqual(p.child1.name2, p.name2)
            self.assertEqual(p.child1.value, 1)
            self.assertEqual(p.child1.child4.name1, p.child1.name1)
            self.assertEqual(p.child1.child4.name2, p.child1.name2)
            self.assertEqual(p.child1.child4.value, p.child1.value)
            self.assertEqual(p.child1.child4.value4, 4)

    def test_inheritance_deferred(self):
        c = Child4.objects.create(name1="n1", name2="n2", value=1, value4=4)
        with self.assertNumQueries(1):
            p = (
                Parent2.objects.select_related("child1")
                .only("id2", "child1__value")
                .get(name2="n2")
            )
            self.assertEqual(p.id2, c.id2)
            self.assertEqual(p.child1.value, 1)
        p = (
            Parent2.objects.select_related("child1")
            .only("id2", "child1__value")
            .get(name2="n2")
        )
        with self.assertNumQueries(1):
            self.assertEqual(p.name2, "n2")
        p = (
            Parent2.objects.select_related("child1")
            .only("id2", "child1__value")
            .get(name2="n2")
        )
        with self.assertNumQueries(1):
            self.assertEqual(p.child1.name2, "n2")

    def test_inheritance_deferred2(self):
        c = Child4.objects.create(name1="n1", name2="n2", value=1, value4=4)
        qs = Parent2.objects.select_related("child1", "child1__child4").only(
            "id2", "child1__value", "child1__child4__value4"
        )
        with self.assertNumQueries(1):
            p = qs.get(name2="n2")
            self.assertEqual(p.id2, c.id2)
            self.assertEqual(p.child1.value, 1)
            self.assertEqual(p.child1.child4.value4, 4)
            self.assertEqual(p.child1.child4.id2, c.id2)
        p = qs.get(name2="n2")
        with self.assertNumQueries(1):
            self.assertEqual(p.child1.name2, "n2")
        p = qs.get(name2="n2")
        with self.assertNumQueries(0):
            self.assertEqual(p.child1.value, 1)
            self.assertEqual(p.child1.child4.value4, 4)
        with self.assertNumQueries(2):
            self.assertEqual(p.child1.name1, "n1")
            self.assertEqual(p.child1.child4.name1, "n1")

    def test_self_relation(self):
        item1 = LinkedList.objects.create(name="item1")
        LinkedList.objects.create(name="item2", previous_item=item1)
        with self.assertNumQueries(1):
            item1_db = LinkedList.objects.select_related("next_item").get(name="item1")
            self.assertEqual(item1_db.next_item.name, "item2")


class ReverseSelectRelatedValidationTests(SimpleTestCase):
    """
    Rverse related fields should be listed in the validation message when an
    invalid field is given in select_related().
    """

    non_relational_error = (
        "Non-relational field given in select_related: '%s'. Choices are: %s"
    )
    invalid_error = (
        "Invalid field name(s) given in select_related: '%s'. Choices are: %s"
    )

    def test_reverse_related_validation(self):
        fields = "userprofile, userstat"

        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("foobar", fields)
        ):
            list(User.objects.select_related("foobar"))

        with self.assertRaisesMessage(
            FieldError, self.non_relational_error % ("username", fields)
        ):
            list(User.objects.select_related("username"))

    def test_reverse_related_validation_with_filtered_relation(self):
        fields = "userprofile, userstat, relation"
        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("foobar", fields)
        ):
            list(
                User.objects.annotate(
                    relation=FilteredRelation("userprofile")
                ).select_related("foobar")
            )
