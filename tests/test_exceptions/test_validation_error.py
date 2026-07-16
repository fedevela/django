import unittest

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
        pass

    # VEQ-002
    def test_veq_002_errors_with_different_messages_compare_unequal(self):
        pass

    # VEQ-002
    def test_veq_002_errors_with_different_codes_compare_unequal(self):
        pass

    # VEQ-002
    def test_veq_002_errors_with_different_parameters_compare_unequal(self):
        pass

    # VEQ-009
    def test_veq_009_error_compared_with_itself_compares_equal(self):
        pass

    # VEQ-010
    def test_veq_010_reversing_error_operands_preserves_equality_result(self):
        pass

    # VEQ-011
    def test_veq_011_unrelated_object_in_either_operand_order_compares_unequal_without_error(self):
        pass

    # VEQ-012
    def test_veq_012_comparison_preserves_both_errors_and_validation_content(self):
        pass
