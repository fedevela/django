import datetime
import json

from django import forms
from django.core import exceptions, serializers
from django.db import models
from django.test import SimpleTestCase, TestCase

from .models import DurationModel, NullDurationModel


class TestSaveLoad(TestCase):

    def test_simple_roundtrip(self):
        duration = datetime.timedelta(microseconds=8999999999999999)
        DurationModel.objects.create(field=duration)
        loaded = DurationModel.objects.get()
        self.assertEqual(loaded.field, duration)

    def test_create_empty(self):
        NullDurationModel.objects.create()
        loaded = NullDurationModel.objects.get()
        self.assertIsNone(loaded.field)

    def test_fractional_seconds(self):
        value = datetime.timedelta(seconds=2.05)
        d = DurationModel.objects.create(field=value)
        d.refresh_from_db()
        self.assertEqual(d.field, value)


class TestQuerying(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.objs = [
            DurationModel.objects.create(field=datetime.timedelta(days=1)),
            DurationModel.objects.create(field=datetime.timedelta(seconds=1)),
            DurationModel.objects.create(field=datetime.timedelta(seconds=-1)),
        ]

    def test_exact(self):
        self.assertSequenceEqual(
            DurationModel.objects.filter(field=datetime.timedelta(days=1)),
            [self.objs[0]]
        )

    def test_gt(self):
        self.assertSequenceEqual(
            DurationModel.objects.filter(field__gt=datetime.timedelta(days=0)),
            [self.objs[0], self.objs[1]]
        )


class TestSerialization(SimpleTestCase):
    test_data = '[{"fields": {"field": "1 01:00:00"}, "model": "model_fields.durationmodel", "pk": null}]'

    def test_dumping(self):
        instance = DurationModel(field=datetime.timedelta(days=1, hours=1))
        data = serializers.serialize('json', [instance])
        self.assertEqual(json.loads(data), json.loads(self.test_data))

    def test_loading(self):
        instance = list(serializers.deserialize('json', self.test_data))[0].object
        self.assertEqual(instance.field, datetime.timedelta(days=1, hours=1))


class TestValidation(SimpleTestCase):
    def test_dur_003_invalid_input_preserves_invalid_duration_validation_condition(self):
        """GUID: DUR-003"""
        value = 'not a duration'
        field = models.DurationField()

        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(value, None)

        self.assertEqual(cm.exception.code, 'invalid')
        self.assertEqual(cm.exception.params, {'value': value})

    def test_dur_004_14_00_parses_as_00_14_00_representing_14_minutes(self):
        """GUID: DUR-004"""
        field = models.DurationField()

        self.assertEqual(field.clean('14:00', None), datetime.timedelta(minutes=14))

    def test_dur_005_previously_accepted_input_preserves_parsed_value(self):
        """GUID: DUR-005"""
        field = models.DurationField()
        test_values = (
            ('30', datetime.timedelta(seconds=30)),
            ('15:30.1', datetime.timedelta(minutes=15, seconds=30, milliseconds=100)),
            ('1:15:30', datetime.timedelta(hours=1, minutes=15, seconds=30)),
            ('4 10:15:30', datetime.timedelta(days=4, hours=10, minutes=15, seconds=30)),
            ('-15:30', datetime.timedelta(minutes=-15, seconds=-30)),
            ('P4D', datetime.timedelta(days=4)),
            ('PT0.000005S', datetime.timedelta(microseconds=5)),
            ('1 day 0:00:01', datetime.timedelta(days=1, seconds=1)),
        )

        for value, expected in test_values:
            with self.subTest(value=value):
                self.assertEqual(field.clean(value, None), expected)

    def test_invalid_string(self):
        field = models.DurationField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean('not a datetime', None)
        self.assertEqual(cm.exception.code, 'invalid')
        self.assertEqual(
            cm.exception.message % cm.exception.params,
            "'not a datetime' value has an invalid format. "
            "It must be in [DD] [[HH:]MM:]ss[.uuuuuu] format."
        )


class TestFormField(SimpleTestCase):
    # Tests for forms.DurationField are in the forms_tests app.

    def test_formfield(self):
        field = models.DurationField()
        self.assertIsInstance(field.formfield(), forms.DurationField)
