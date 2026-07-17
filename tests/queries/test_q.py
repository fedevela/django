from django.db.models import F, Q
from django.test import SimpleTestCase


class QTests(SimpleTestCase):
    def test_combine_and_empty(self):
        q = Q(x=1)
        self.assertEqual(q & Q(), q)
        self.assertEqual(Q() & q, q)

    def test_combine_and_both_empty(self):
        self.assertEqual(Q() & Q(), Q())

    def test_combine_or_empty(self):
        q = Q(x=1)
        self.assertEqual(q | Q(), q)
        self.assertEqual(Q() | q, q)

    def test_combine_or_both_empty(self):
        self.assertEqual(Q() | Q(), Q())

    def test_qcomb_001_empty_or_dict_keys_does_not_require_pickling(self):
        """QCOMB-001: Empty OR with dict_keys completes without pickling."""
        Q() | Q(x__in={}.keys())

    def test_qcomb_002_empty_or_retains_original_condition_and_value(self):
        """QCOMB-002: Empty OR retains the x__in condition and value."""
        value = {}.keys()

        combined = Q() | Q(x__in=value)

        self.assertEqual(combined.children[0][0], 'x__in')
        self.assertIs(combined.children[0][1], value)

    def test_qcomb_003_empty_or_preserves_identity_in_both_operand_orders(self):
        """QCOMB-003: Empty OR preserves identity-like operand semantics."""
        q = Q(x__in={}.keys())

        self.assertEqual(Q() | q, q)
        self.assertEqual(q | Q(), q)

    def test_qcomb_005_empty_or_does_not_mutate_operands_or_value(self):
        """QCOMB-005: Empty OR leaves both operands and their value unchanged."""
        empty = Q()
        value = {}.keys()
        q = Q(x__in=value)
        empty_children = empty.children[:]
        q_children = q.children[:]

        left_combined = empty | q
        right_combined = q | empty

        self.assertEqual(empty.children, empty_children)
        self.assertEqual(q.children, q_children)
        self.assertIs(q.children[0][1], value)
        self.assertIs(left_combined.children[0][1], value)
        self.assertIs(right_combined.children[0][1], value)
        self.assertIsNot(left_combined.children, q.children)
        self.assertIsNot(right_combined.children, q.children)

    def test_qcomb_006_empty_or_accepts_standalone_non_pickleable_value(self):
        """QCOMB-006: Empty OR doesn't reject an accepted non-pickleable value."""
        class NonPickleable:
            def __reduce__(self):
                raise TypeError('cannot be pickled')

        value = NonPickleable()
        q = Q(x__in=value)

        self.assertIs((q | Q()).children[0][1], value)

    def test_combine_not_q_object(self):
        obj = object()
        q = Q(x=1)
        with self.assertRaisesMessage(TypeError, str(obj)):
            q | obj
        with self.assertRaisesMessage(TypeError, str(obj)):
            q & obj

    def test_deconstruct(self):
        q = Q(price__gt=F('discounted_price'))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(path, 'django.db.models.Q')
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {'price__gt': F('discounted_price')})

    def test_deconstruct_negated(self):
        q = ~Q(price__gt=F('discounted_price'))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {
            'price__gt': F('discounted_price'),
            '_negated': True,
        })

    def test_deconstruct_or(self):
        q1 = Q(price__gt=F('discounted_price'))
        q2 = Q(price=F('discounted_price'))
        q = q1 | q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (
            ('price__gt', F('discounted_price')),
            ('price', F('discounted_price')),
        ))
        self.assertEqual(kwargs, {'_connector': 'OR'})

    def test_deconstruct_and(self):
        q1 = Q(price__gt=F('discounted_price'))
        q2 = Q(price=F('discounted_price'))
        q = q1 & q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (
            ('price__gt', F('discounted_price')),
            ('price', F('discounted_price')),
        ))
        self.assertEqual(kwargs, {})

    def test_deconstruct_multiple_kwargs(self):
        q = Q(price__gt=F('discounted_price'), price=F('discounted_price'))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (
            ('price', F('discounted_price')),
            ('price__gt', F('discounted_price')),
        ))
        self.assertEqual(kwargs, {})

    def test_deconstruct_nested(self):
        q = Q(Q(price__gt=F('discounted_price')))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (Q(price__gt=F('discounted_price')),))
        self.assertEqual(kwargs, {})

    def test_reconstruct(self):
        q = Q(price__gt=F('discounted_price'))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_negated(self):
        q = ~Q(price__gt=F('discounted_price'))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_or(self):
        q1 = Q(price__gt=F('discounted_price'))
        q2 = Q(price=F('discounted_price'))
        q = q1 | q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_and(self):
        q1 = Q(price__gt=F('discounted_price'))
        q2 = Q(price=F('discounted_price'))
        q = q1 & q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)
