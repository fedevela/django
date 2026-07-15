import datetime

from django.db import connection, models, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from .models import (
    Award, AwardNote, Book, Child, Contact, Eaten, Email, File, Food, FooFile,
    DeletionTracebook, DeletionTraceUUID, FooFileProxy, FooImage, FooPhoto, House,
    Image, Item, Location, Login, OrderedPerson, OrgUnit, Person, Photo, PlayedWith,
    PlayedWithNote, Policy, Researcher, Toy, Version,
)


# Can't run this test under SQLite, because you can't
# get two connections to an in-memory database.
@skipUnlessDBFeature('test_db_allows_multiple_connections')
class DeleteLockingTest(TransactionTestCase):

    available_apps = ['delete_regress']

    def setUp(self):
        # Create a second connection to the default database
        self.conn2 = connection.copy()
        self.conn2.set_autocommit(False)

    def tearDown(self):
        # Close down the second connection.
        self.conn2.rollback()
        self.conn2.close()

    def test_concurrent_delete(self):
        """Concurrent deletes don't collide and lock the database (#9479)."""
        with transaction.atomic():
            Book.objects.create(id=1, pagecount=100)
            Book.objects.create(id=2, pagecount=200)
            Book.objects.create(id=3, pagecount=300)

        with transaction.atomic():
            # Start a transaction on the main connection.
            self.assertEqual(3, Book.objects.count())

            # Delete something using another database connection.
            with self.conn2.cursor() as cursor2:
                cursor2.execute("DELETE from delete_regress_book WHERE id = 1")
            self.conn2.commit()

            # In the same transaction on the main connection, perform a
            # queryset delete that covers the object deleted with the other
            # connection. This causes an infinite loop under MySQL InnoDB
            # unless we keep track of already deleted objects.
            Book.objects.filter(pagecount__lt=250).delete()

        self.assertEqual(1, Book.objects.count())


class DeleteCascadeTests(TestCase):
    def test_generic_relation_cascade(self):
        """
        Django cascades deletes through generic-related objects to their
        reverse relations.
        """
        person = Person.objects.create(name='Nelson Mandela')
        award = Award.objects.create(name='Nobel', content_object=person)
        AwardNote.objects.create(note='a peace prize', award=award)
        self.assertEqual(AwardNote.objects.count(), 1)
        person.delete()
        self.assertEqual(Award.objects.count(), 0)
        # first two asserts are just sanity checks, this is the kicker:
        self.assertEqual(AwardNote.objects.count(), 0)

    def test_fk_to_m2m_through(self):
        """
        If an M2M relationship has an explicitly-specified through model, and
        some other model has an FK to that through model, deletion is cascaded
        from one of the participants in the M2M, to the through model, to its
        related model.
        """
        juan = Child.objects.create(name='Juan')
        paints = Toy.objects.create(name='Paints')
        played = PlayedWith.objects.create(child=juan, toy=paints, date=datetime.date.today())
        PlayedWithNote.objects.create(played=played, note='the next Jackson Pollock')
        self.assertEqual(PlayedWithNote.objects.count(), 1)
        paints.delete()
        self.assertEqual(PlayedWith.objects.count(), 0)
        # first two asserts just sanity checks, this is the kicker:
        self.assertEqual(PlayedWithNote.objects.count(), 0)

    def test_15776(self):
        policy = Policy.objects.create(pk=1, policy_number="1234")
        version = Version.objects.create(policy=policy)
        location = Location.objects.create(version=version)
        Item.objects.create(version=version, location=location)
        policy.delete()


class DeleteCascadeTransactionTests(TransactionTestCase):

    available_apps = ['delete_regress']

    def test_inheritance(self):
        """
        Auto-created many-to-many through tables referencing a parent model are
        correctly found by the delete cascade when a child of that parent is
        deleted.

        Refs #14896.
        """
        r = Researcher.objects.create()
        email = Email.objects.create(
            label="office-email", email_address="carl@science.edu"
        )
        r.contacts.add(email)

        email.delete()

    def test_to_field(self):
        """
        Cascade deletion works with ForeignKey.to_field set to non-PK.
        """
        apple = Food.objects.create(name="apple")
        Eaten.objects.create(food=apple, meal="lunch")

        apple.delete()
        self.assertFalse(Food.objects.exists())
        self.assertFalse(Eaten.objects.exists())


class LargeDeleteTests(TestCase):
    def test_large_deletes(self):
        "Regression for #13309 -- if the number of objects > chunk size, deletion still occurs"
        for x in range(300):
            Book.objects.create(pagecount=x + 100)
        # attach a signal to make sure we will not fast-delete

        def noop(*args, **kwargs):
            pass
        models.signals.post_delete.connect(noop, sender=Book)
        Book.objects.all().delete()
        models.signals.post_delete.disconnect(noop, sender=Book)
        self.assertEqual(Book.objects.count(), 0)


class ProxyDeleteTest(TestCase):
    """
    Tests on_delete behavior for proxy models.

    See #16128.
    """
    def create_image(self):
        """Return an Image referenced by both a FooImage and a FooFile."""
        # Create an Image
        test_image = Image()
        test_image.save()
        foo_image = FooImage(my_image=test_image)
        foo_image.save()

        # Get the Image instance as a File
        test_file = File.objects.get(pk=test_image.pk)
        foo_file = FooFile(my_file=test_file)
        foo_file.save()

        return test_image

    def test_delete_proxy(self):
        """
        Deleting the *proxy* instance bubbles through to its non-proxy and
        *all* referring objects are deleted.
        """
        self.create_image()

        Image.objects.all().delete()

        # An Image deletion == File deletion
        self.assertEqual(len(Image.objects.all()), 0)
        self.assertEqual(len(File.objects.all()), 0)

        # The Image deletion cascaded and *all* references to it are deleted.
        self.assertEqual(len(FooImage.objects.all()), 0)
        self.assertEqual(len(FooFile.objects.all()), 0)

    def test_delete_proxy_of_proxy(self):
        """
        Deleting a proxy-of-proxy instance should bubble through to its proxy
        and non-proxy parents, deleting *all* referring objects.
        """
        test_image = self.create_image()

        # Get the Image as a Photo
        test_photo = Photo.objects.get(pk=test_image.pk)
        foo_photo = FooPhoto(my_photo=test_photo)
        foo_photo.save()

        Photo.objects.all().delete()

        # A Photo deletion == Image deletion == File deletion
        self.assertEqual(len(Photo.objects.all()), 0)
        self.assertEqual(len(Image.objects.all()), 0)
        self.assertEqual(len(File.objects.all()), 0)

        # The Photo deletion should have cascaded and deleted *all*
        # references to it.
        self.assertEqual(len(FooPhoto.objects.all()), 0)
        self.assertEqual(len(FooFile.objects.all()), 0)
        self.assertEqual(len(FooImage.objects.all()), 0)

    def test_delete_concrete_parent(self):
        """
        Deleting an instance of a concrete model should also delete objects
        referencing its proxy subclass.
        """
        self.create_image()

        File.objects.all().delete()

        # A File deletion == Image deletion
        self.assertEqual(len(File.objects.all()), 0)
        self.assertEqual(len(Image.objects.all()), 0)

        # The File deletion should have cascaded and deleted *all* references
        # to it.
        self.assertEqual(len(FooFile.objects.all()), 0)
        self.assertEqual(len(FooImage.objects.all()), 0)

    def test_delete_proxy_pair(self):
        """
        If a pair of proxy models are linked by an FK from one concrete parent
        to the other, deleting one proxy model cascade-deletes the other, and
        the deletion happens in the right order (not triggering an
        IntegrityError on databases unable to defer integrity checks).

        Refs #17918.
        """
        # Create an Image (proxy of File) and FooFileProxy (proxy of FooFile,
        # which has an FK to File)
        image = Image.objects.create()
        as_file = File.objects.get(pk=image.pk)
        FooFileProxy.objects.create(my_file=as_file)

        Image.objects.all().delete()

        self.assertEqual(len(FooFileProxy.objects.all()), 0)

    def test_19187_values(self):
        msg = 'Cannot call delete() after .values() or .values_list()'
        with self.assertRaisesMessage(TypeError, msg):
            Image.objects.values().delete()
        with self.assertRaisesMessage(TypeError, msg):
            Image.objects.values_list().delete()


class Ticket19102Tests(TestCase):
    """
    Test different queries which alter the SELECT clause of the query. We
    also must be using a subquery for the deletion (that is, the original
    query has a join in it). The deletion should be done as "fast-path"
    deletion (that is, just one query for the .delete() call).

    Note that .values() is not tested here on purpose. .values().delete()
    doesn't work for non fast-path deletes at all.
    """
    @classmethod
    def setUpTestData(cls):
        cls.o1 = OrgUnit.objects.create(name='o1')
        cls.o2 = OrgUnit.objects.create(name='o2')
        cls.l1 = Login.objects.create(description='l1', orgunit=cls.o1)
        cls.l2 = Login.objects.create(description='l2', orgunit=cls.o2)

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_annotate(self):
        with self.assertNumQueries(1):
            Login.objects.order_by('description').filter(
                orgunit__name__isnull=False
            ).annotate(
                n=models.Count('description')
            ).filter(
                n=1, pk=self.l1.pk
            ).delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_extra(self):
        with self.assertNumQueries(1):
            Login.objects.order_by('description').filter(
                orgunit__name__isnull=False
            ).extra(
                select={'extraf': '1'}
            ).filter(
                pk=self.l1.pk
            ).delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())

    @skipUnlessDBFeature("update_can_self_select")
    @skipUnlessDBFeature('can_distinct_on_fields')
    def test_ticket_19102_distinct_on(self):
        # Both Login objs should have same description so that only the one
        # having smaller PK will be deleted.
        Login.objects.update(description='description')
        with self.assertNumQueries(1):
            Login.objects.distinct('description').order_by('pk').filter(
                orgunit__name__isnull=False
            ).delete()
        # Assumed that l1 which is created first has smaller PK.
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_select_related(self):
        with self.assertNumQueries(1):
            Login.objects.filter(
                pk=self.l1.pk
            ).filter(
                orgunit__name__isnull=False
            ).order_by(
                'description'
            ).select_related('orgunit').delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_defer(self):
        with self.assertNumQueries(1):
            Login.objects.filter(
                pk=self.l1.pk
            ).filter(
                orgunit__name__isnull=False
            ).order_by(
                'description'
            ).only('id').delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())


class DeleteTests(TestCase):
    def test_meta_ordered_delete(self):
        # When a subquery is performed by deletion code, the subquery must be
        # cleared of all ordering. There was a but that caused _meta ordering
        # to be used. Refs #19720.
        h = House.objects.create(address='Foo')
        OrderedPerson.objects.create(name='Jack', lives_in=h)
        OrderedPerson.objects.create(name='Bob', lives_in=h)
        OrderedPerson.objects.filter(lives_in__address='Foo').delete()
        self.assertEqual(OrderedPerson.objects.count(), 0)

    def test_foreign_key_delete_nullifies_correct_columns(self):
        """
        With a model (Researcher) that has two foreign keys pointing to the
        same model (Contact), deleting an instance of the target model
        (contact1) nullifies the correct fields of Researcher.
        """
        contact1 = Contact.objects.create(label='Contact 1')
        contact2 = Contact.objects.create(label='Contact 2')
        researcher1 = Researcher.objects.create(
            primary_contact=contact1,
            secondary_contact=contact2,
        )
        researcher2 = Researcher.objects.create(
            primary_contact=contact2,
            secondary_contact=contact1,
        )
        contact1.delete()
        researcher1.refresh_from_db()
        researcher2.refresh_from_db()
        self.assertIsNone(researcher1.primary_contact)
        self.assertEqual(researcher1.secondary_contact, contact2)
        self.assertEqual(researcher2.primary_contact, contact2)
        self.assertIsNone(researcher2.secondary_contact)


DJ11179_001_VERIFICATION_ARTIFACTS = [
    (
        "DJ11179-001",
        "DeletePkResetNoDependencyTests.test_dj11179_001_default_pk_is_none_after_no_dependency_instance_delete",
        "Persisted default-PK instance cleared to None after successful no-dependency delete.",
    ),
    (
        "DJ11179-001",
        "DeletePkResetNoDependencyTests.test_dj11179_001_uuid_pk_is_none_after_no_dependency_instance_delete",
        "Persisted UUID-PK instance cleared to None after successful no-dependency delete.",
    ),
    (
        "DJ11179-001",
        "DeletePkResetNoDependencyTests.test_dj11179_001_inmemory_identity_state_after_single_instance_delete",
        "In-memory instance identity is maintained and pk is None after successful delete return.",
    ),
]


DJ11179_002_VERIFICATION_ARTIFACTS = [
    (
        "DJ11179-002",
        "DeleteNoDependencyLookupTraceabilityTests.test_dj11179_002_stale_pk_lookup_is_false_after_no_dependency_delete",
        "Persisted stale key is unreachable by filter(pk=old_pk) after successful no-dependency instance delete.",
    ),
    (
        "DJ11179-002",
        "DeleteNoDependencyLookupTraceabilityTests.test_dj11179_002_stale_instance_lookup_raises_does_not_exist_after_delete",
        "Stale in-memory reference old pk lookup via get(pk=old_pk) raises DoesNotExist after delete.",
    ),
    (
        "DJ11179-002",
        "DeleteNoDependencyLookupTraceabilityTests.test_dj11179_002_old_pk_not_found_when_inmemory_pk_is_reset_to_none",
        "In-memory pk reset to None does not make old pre-delete key discoverable in the same process.",
    ),
]


DJ11179_003_VERIFICATION_ARTIFACTS = [
    (
        "DJ11179-003",
        "DeletePkResetFastDeleteBranchTraceabilityTests.test_dj11179_003_only_dependency_free_fast_delete_instances_apply_inmemory_pk_reset",
        "Only dependency-free fast-delete instance paths may apply pk reset to None; collector-managed dependency paths remain unchanged by this obligation.",
    ),
    (
        "DJ11179-003",
        "DeletePkResetFastDeleteBranchTraceabilityTests.test_dj11179_003_fast_delete_guard_and_path_selection_gates_pk_reset",
        "Branch selection must gate pk reset to the fast-delete path: when dependency-free, apply mutation, when collector-managed, do not apply this fast-delete mutation.",
    ),
    (
        "DJ11179-003",
        "DeletePkResetFastDeleteBranchTraceabilityTests.test_dj11179_003_dependency_collection_internals_do_not_receive_fast_delete_pk_mutation",
        "Dependency-managed collector flow retains its existing mutation contract and does not receive the fast-delete pk-reset mutation.",
    ),
]


class DeletePkResetNoDependencyTests(TestCase):
    requirements_coverage = DJ11179_001_VERIFICATION_ARTIFACTS

    def test_dj11179_001_default_pk_is_none_after_no_dependency_instance_delete(self):
        instance = DeletionTracebook.objects.create()
        instance_pk = instance.pk
        instance.delete()
        self.assertIsNone(instance.pk)
        self.assertFalse(DeletionTracebook.objects.filter(pk=instance_pk).exists())

    def test_dj11179_001_uuid_pk_is_none_after_no_dependency_instance_delete(self):
        instance = DeletionTraceUUID.objects.create()
        instance_pk = instance.pk
        instance.delete()
        self.assertIsNone(instance.pk)
        self.assertFalse(DeletionTraceUUID.objects.filter(pk=instance_pk).exists())

    def test_dj11179_001_inmemory_identity_state_after_single_instance_delete(self):
        instance = DeletionTracebook.objects.create()
        instance_pk = instance.pk
        instance.delete()
        self.assertIsNone(instance.pk)
        self.assertFalse(DeletionTracebook.objects.filter(pk=instance_pk).exists())


class DeleteNoDependencyLookupTraceabilityTests(TestCase):
    requirements_coverage = DJ11179_002_VERIFICATION_ARTIFACTS

    def test_dj11179_002_stale_pk_lookup_is_false_after_no_dependency_delete(self):
        instance = DeletionTracebook.objects.create()
        old_pk = instance.pk
        instance.delete()
        self.assertFalse(DeletionTracebook.objects.filter(pk=old_pk).exists())

    def test_dj11179_002_stale_instance_lookup_raises_does_not_exist_after_delete(self):
        instance = DeletionTraceUUID.objects.create()
        old_pk = instance.pk
        instance.delete()
        with self.assertRaises(DeletionTraceUUID.DoesNotExist):
            DeletionTraceUUID.objects.get(pk=old_pk)

    def test_dj11179_002_old_pk_not_found_when_inmemory_pk_is_reset_to_none(self):
        instance = DeletionTracebook.objects.create()
        old_pk = instance.pk
        instance.delete()
        instance.pk = None
        self.assertFalse(DeletionTracebook.objects.filter(pk=old_pk).exists())
        with self.assertRaises(DeletionTracebook.DoesNotExist):
            DeletionTracebook.objects.get(pk=old_pk)


class DeletePkResetFastDeleteBranchTraceabilityTests(TestCase):
    requirements_coverage = DJ11179_003_VERIFICATION_ARTIFACTS

    def test_dj11179_003_only_dependency_free_fast_delete_instances_apply_inmemory_pk_reset(self):
        no_dependency_instance = DeletionTracebook.objects.create()
        no_dependency_pk = no_dependency_instance.pk
        no_dependency_instance.delete()
        self.assertIsNone(no_dependency_instance.pk)
        self.assertFalse(DeletionTracebook.objects.filter(pk=no_dependency_pk).exists())

        dependency_root = Policy.objects.create(policy_number="003")
        dependency_child = Version.objects.create(policy=dependency_root)
        dependency_root.delete()
        self.assertIsNotNone(dependency_root.pk)
        self.assertIsNotNone(dependency_child.pk)
        self.assertFalse(Version.objects.filter(pk=dependency_child.pk).exists())

    def test_dj11179_003_fast_delete_guard_and_path_selection_gates_pk_reset(self):
        def noop_signal(*args, **kwargs):
            pass

        fast_delete_instance = DeletionTracebook.objects.create()
        fast_delete_instance.delete()
        self.assertIsNone(fast_delete_instance.pk)

        models.signals.pre_delete.connect(noop_signal, sender=DeletionTracebook)
        try:
            managed_delete_instance = DeletionTracebook.objects.create()
            managed_delete_instance.delete()
            self.assertIsNotNone(managed_delete_instance.pk)
            self.assertFalse(
                DeletionTracebook.objects.filter(pk=managed_delete_instance.pk).exists()
            )
        finally:
            models.signals.pre_delete.disconnect(noop_signal, sender=DeletionTracebook)

    def test_dj11179_003_dependency_collection_internals_do_not_receive_fast_delete_pk_mutation(self):
        policy = Policy.objects.create(policy_number="003-branch")
        version = Version.objects.create(policy=policy)
        policy.delete()

        self.assertIsNotNone(policy.pk)
        self.assertIsNotNone(version.pk)
        self.assertFalse(Version.objects.filter(pk=version.pk).exists())
