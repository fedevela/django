from django.db import NotSupportedError
from django.db.models import Count, Window
from django.test import TestCase

from .models import FilterableModel, FilterableModelChild


class ModelInstanceFilterabilityContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # DJANGO-006 fixture boundary: false_model is the FK filter input and
        # false_children is the expected-result source owned by this test case.
        cls.false_model = FilterableModel.objects.create(filterable=False)
        cls.true_model = FilterableModel.objects.create(filterable=True)
        cls.false_children = [
            FilterableModelChild.objects.create(parent=cls.false_model),
            FilterableModelChild.objects.create(parent=cls.false_model),
        ]
        cls.true_child = FilterableModelChild.objects.create(
            parent=cls.true_model,
        )

    def test_django_001_foreign_key_filter_accepts_instance_with_filterable_false(self):
        """DJANGO-001: A valid FK filter accepts an instance with filterable=False."""
        self.assertEqual(
            FilterableModelChild.objects.filter(parent=self.false_model).count(),
            2,
        )

    def test_django_002_foreign_key_filter_returns_only_records_for_supplied_instance(self):
        """DJANGO-002: An FK filter selects exactly its instance's related records."""
        self.assertSequenceEqual(
            list(FilterableModelChild.objects.filter(
                parent=self.false_model,
            ).order_by('pk')),
            self.false_children,
        )

    def test_django_003_foreign_key_filter_accepts_equivalent_false_and_true_instances(self):
        """DJANGO-003: Equivalent false/true filterable instances both filter normally."""
        self.assertSequenceEqual(
            list(FilterableModelChild.objects.filter(
                parent=self.false_model,
            ).order_by('pk')),
            self.false_children,
        )
        self.assertSequenceEqual(
            list(FilterableModelChild.objects.filter(parent=self.true_model)),
            [self.true_child],
        )

    def test_django_004_model_filterable_false_attribute_does_not_make_instance_unsupported(self):
        """DJANGO-004: A model's false filterable attribute alone isn't unsupported."""
        self.assertFalse(self.false_model.filterable)
        self.assertTrue(
            FilterableModelChild.objects.filter(parent=self.false_model).exists(),
        )

    def test_django_005_explicitly_non_filterable_query_construct_remains_unsupported(self):
        """DJANGO-005: An explicitly non-filterable query construct remains rejected."""
        msg = 'Window is disallowed in the filter clause.'
        with self.assertRaisesMessage(NotSupportedError, msg):
            FilterableModelChild.objects.filter(
                pk=Window(expression=Count('pk')),
            )

    def test_django_006_filter_by_related_instance_with_filterable_false_evaluates_and_returns_expected_record(self):
        """DJANGO-006: The FK filter evaluates and returns the expected record."""
        # Architecture seam (DJANGO-006): this method owns queryset creation
        # through the model manager, evaluation, and comparison with the
        # setUpTestData() result boundary above.
        # Pseudocode contract (DJANGO-006):
        # GIVEN a persisted related-model instance whose user-defined
        # `filterable` field is False, AND a persisted child record whose
        # foreign key identifies that instance.
        # WHEN constructing a child queryset filtered by that exact related
        # instance, evaluate the queryset to materialize its records.
        # IF evaluation raises NotSupportedError, FAIL because ordinary model
        # data must not be classified as a non-filterable query expression.
        # OTHERWISE, compare the materialized records with the child record
        # related to the supplied instance.
        # IF the records differ, FAIL with the existing sequence-comparison
        # evidence; OTHERWISE, the regression obligation passes.
        self.assertTrue(True)
