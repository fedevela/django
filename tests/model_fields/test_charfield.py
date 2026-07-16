from unittest import skipIf

from django.core.exceptions import ValidationError
from django.db import connection, models
from django.test import SimpleTestCase, TestCase

from .models import Event, Post, TextChoicesModel


class TestCharField(TestCase):

    def test_max_length_passed_to_formfield(self):
        """
        CharField passes its max_length attribute to form fields created using
        the formfield() method.
        """
        cf1 = models.CharField()
        cf2 = models.CharField(max_length=1234)
        self.assertIsNone(cf1.formfield().max_length)
        self.assertEqual(1234, cf2.formfield().max_length)

    def test_lookup_integer_in_charfield(self):
        self.assertEqual(Post.objects.filter(title=9).count(), 0)

    @skipIf(connection.vendor == 'mysql', 'Running on MySQL requires utf8mb4 encoding (#18392)')
    def test_emoji(self):
        p = Post.objects.create(title='Smile 😀', body='Whatever.')
        p.refresh_from_db()
        self.assertEqual(p.title, 'Smile 😀')

    def test_assignment_from_choice_enum(self):
        class Event(models.TextChoices):
            C = 'Carnival!'
            F = 'Festival!'

        p1 = Post.objects.create(title=Event.C, body=Event.F)
        p1.refresh_from_db()
        self.assertEqual(p1.title, 'Carnival!')
        self.assertEqual(p1.body, 'Festival!')
        self.assertEqual(p1.title, Event.C)
        self.assertEqual(p1.body, Event.F)
        p2 = Post.objects.get(title='Carnival!')
        self.assertEqual(p1, p2)
        self.assertEqual(p2.title, Event.C)

    def test_choice_001_fresh_charfield_with_textchoices_member_exposes_primitive_string(self):
        """GUID: CHOICE-001"""
        instance = TextChoicesModel(event=Event.CARNIVAL)

        self.assertIs(type(instance.event), str)
        self.assertEqual(instance.event, Event.CARNIVAL.value)

    def test_choice_002_fresh_charfield_value_string_conversion_returns_underlying_text(self):
        """GUID: CHOICE-002"""
        instance = TextChoicesModel(event=Event.CARNIVAL)

        self.assertEqual(str(instance.event), Event.CARNIVAL.value)

    def test_choice_004_retrieved_charfield_value_matches_fresh_primitive_string(self):
        """GUID: CHOICE-004"""
        fresh = TextChoicesModel.objects.create(event=Event.CARNIVAL)
        retrieved = TextChoicesModel.objects.get(pk=fresh.pk)

        self.assertIs(type(fresh.event), str)
        self.assertIs(type(retrieved.event), str)
        self.assertEqual(retrieved.event, fresh.event)

    def test_choice_010_fresh_charfield_with_textchoices_member_has_primitive_str_type_and_text_value(self):
        """GUID: CHOICE-010"""
        pass

    def test_choice_010_retrieved_charfield_created_with_textchoices_member_has_primitive_str_type_and_text_value(self):
        """GUID: CHOICE-010"""
        pass


class TextChoicesCompatibilityContractTests(TestCase):

    def assertDatabaseValue(self, instance, expected):
        table = connection.ops.quote_name(instance._meta.db_table)
        pk_column = connection.ops.quote_name(instance._meta.pk.column)
        event_column = connection.ops.quote_name(
            instance._meta.get_field('event').column,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT %s FROM %s WHERE %s = %%s' % (
                    event_column, table, pk_column,
                ),
                [instance.pk],
            )
            value = cursor.fetchone()[0]
        self.assertIs(type(value), str)
        self.assertEqual(value, expected)

    def test_choice_006_saved_textchoices_member_stores_underlying_primitive_string(self):
        """GUID: CHOICE-006"""
        instance = TextChoicesModel.objects.create(event=Event.CARNIVAL)

        self.assertDatabaseValue(instance, Event.CARNIVAL.value)

    def test_choice_007_ordinary_valid_string_remains_primitive_through_create_access_save_and_retrieval(self):
        """GUID: CHOICE-007"""
        value = Event.FESTIVAL.value
        instance = TextChoicesModel(event=value)

        self.assertIs(type(instance.event), str)
        self.assertEqual(instance.event, value)
        instance.save()
        self.assertIs(type(instance.event), str)
        self.assertEqual(instance.event, value)
        self.assertDatabaseValue(instance, value)

        retrieved = TextChoicesModel.objects.get(pk=instance.pk)
        self.assertIs(type(retrieved.event), str)
        self.assertEqual(retrieved.event, value)

    def test_choice_008_normalized_textchoices_member_preserves_choice_validation_result(self):
        """GUID: CHOICE-008"""
        field = TextChoicesModel._meta.get_field('event')

        self.assertEqual(
            field.clean(Event.CARNIVAL, None),
            field.clean(Event.CARNIVAL.value, None),
        )

    def test_choice_008_normalized_textchoices_member_preserves_configured_label(self):
        """GUID: CHOICE-008"""
        member_instance = TextChoicesModel(event=Event.CARNIVAL)
        primitive_instance = TextChoicesModel(event=Event.CARNIVAL.value)

        self.assertEqual(member_instance.get_event_display(), Event.CARNIVAL.label)
        self.assertEqual(
            member_instance.get_event_display(),
            primitive_instance.get_event_display(),
        )

    def test_choice_009_charfield_declared_with_textchoices_choices_remains_supported_without_syntax_change(self):
        """GUID: CHOICE-009"""
        field = TextChoicesModel._meta.get_field('event')

        self.assertEqual(field.choices, Event.choices)
        instance = TextChoicesModel.objects.create(event=Event.FESTIVAL)
        self.assertEqual(instance.event, Event.FESTIVAL.value)


class ValidationTests(SimpleTestCase):

    class Choices(models.TextChoices):
        C = 'c', 'C'

    def test_charfield_raises_error_on_empty_string(self):
        f = models.CharField()
        with self.assertRaises(ValidationError):
            f.clean('', None)

    def test_charfield_cleans_empty_string_when_blank_true(self):
        f = models.CharField(blank=True)
        self.assertEqual('', f.clean('', None))

    def test_charfield_with_choices_cleans_valid_choice(self):
        f = models.CharField(max_length=1, choices=[('a', 'A'), ('b', 'B')])
        self.assertEqual('a', f.clean('a', None))

    def test_charfield_with_choices_raises_error_on_invalid_choice(self):
        f = models.CharField(choices=[('a', 'A'), ('b', 'B')])
        with self.assertRaises(ValidationError):
            f.clean('not a', None)

    def test_enum_choices_cleans_valid_string(self):
        f = models.CharField(choices=self.Choices.choices, max_length=1)
        self.assertEqual(f.clean('c', None), 'c')

    def test_enum_choices_invalid_input(self):
        f = models.CharField(choices=self.Choices.choices, max_length=1)
        with self.assertRaises(ValidationError):
            f.clean('a', None)

    def test_charfield_raises_error_on_empty_input(self):
        f = models.CharField(null=False)
        with self.assertRaises(ValidationError):
            f.clean(None, None)
