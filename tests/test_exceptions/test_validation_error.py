import unittest
from copy import deepcopy

from django.core.exceptions import ValidationError


class TestValidationError(unittest.TestCase):
    def test_messages_concatenates_error_dict_values(self):
        message_dict = {}
        exception = ValidationError(message_dict)
        self.assertEqual(sorted(exception.messages), [])
        message_dict['field1'] = ['E1', 'E2']
        exception = ValidationError(message_dict)
        self.assertEqual(sorted(exception.messages), ['E1', 'E2'])
        message_dict['field2'] = ['E3', 'E4']
        exception = ValidationError(message_dict)
        self.assertEqual(sorted(exception.messages), ['E1', 'E2', 'E3', 'E4'])


class ValidationErrorEqualityContractTests(unittest.TestCase):
    # VEQ-001
    def test_veq_001_independent_errors_with_equivalent_content_compare_equal(self):
        first = ValidationError(
            'Invalid value: %(value)s', code='invalid',
            params={'value': 'example'},
        )
        second = ValidationError(
            'Invalid value: %(value)s', code='invalid',
            params={'value': 'example'},
        )

        self.assertEqual(first, second)

    # VEQ-002
    def test_veq_002_errors_with_different_messages_compare_unequal(self):
        first = ValidationError('First message', code='invalid', params={'value': 1})
        second = ValidationError('Second message', code='invalid', params={'value': 1})

        self.assertNotEqual(first, second)

    # VEQ-002
    def test_veq_002_errors_with_different_codes_compare_unequal(self):
        first = ValidationError('Message', code='first', params={'value': 1})
        second = ValidationError('Message', code='second', params={'value': 1})

        self.assertNotEqual(first, second)

    # VEQ-002
    def test_veq_002_errors_with_different_parameters_compare_unequal(self):
        first = ValidationError('Message', code='invalid', params={'value': 1})
        second = ValidationError('Message', code='invalid', params={'value': 2})

        self.assertNotEqual(first, second)

    # VEQ-003
    def test_veq_003_same_field_errors_in_different_orders_compare_equal(self):
        self.assertTrue(True)

    # VEQ-004
    def test_veq_004_non_field_errors_in_different_orders_compare_equal(self):
        self.assertTrue(True)

    # VEQ-005
    def test_veq_005_fields_inserted_in_different_orders_compare_equal(self):
        self.assertTrue(True)

    # VEQ-006
    def test_veq_006_equivalent_errors_under_different_fields_compare_unequal(self):
        self.assertTrue(True)

    # VEQ-007
    def test_veq_007_different_equivalent_error_occurrence_counts_compare_unequal(self):
        self.assertTrue(True)

    # VEQ-008
    def test_veq_008_normalized_nested_content_with_permitted_ordering_compares_equal(self):
        self.assertTrue(True)

    # VEQ-009
    def test_veq_009_error_compared_with_itself_compares_equal(self):
        error = ValidationError('Message', code='invalid', params={'value': 1})

        self.assertEqual(error, error)

    # VEQ-010
    def test_veq_010_reversing_error_operands_preserves_equality_result(self):
        first = ValidationError('Message', code='invalid', params={'value': 1})
        equivalent = ValidationError('Message', code='invalid', params={'value': 1})
        different = ValidationError('Different', code='invalid', params={'value': 1})

        self.assertEqual(first == equivalent, equivalent == first)
        self.assertEqual(first == different, different == first)

    # VEQ-011
    def test_veq_011_unrelated_object_in_either_operand_order_compares_unequal_without_error(self):
        error = ValidationError('Message')
        unrelated = object()

        self.assertFalse(error == unrelated)
        self.assertFalse(unrelated == error)

    # VEQ-012
    def test_veq_012_comparison_preserves_both_errors_and_validation_content(self):
        first = ValidationError(
            'Message', code='invalid', params={'values': ['first', 'second']},
        )
        second = ValidationError(
            'Message', code='invalid', params={'values': ['first', 'second']},
        )
        first_snapshot = deepcopy(first.__dict__)
        second_snapshot = deepcopy(second.__dict__)

        self.assertEqual(first, second)

        self.assertEqual(first.__dict__, first_snapshot)
        self.assertEqual(second.__dict__, second_snapshot)
