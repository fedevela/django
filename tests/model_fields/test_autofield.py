from django.db import models
from django.test import SimpleTestCase

from .models import AutoModel, BigAutoModel, SmallAutoModel
from .test_integerfield import (
    BigIntegerFieldTests, IntegerFieldTests, SmallIntegerFieldTests,
)


class AutoFieldTests(IntegerFieldTests):
    model = AutoModel
    rel_db_type_class = models.IntegerField


class BigAutoFieldTests(BigIntegerFieldTests):
    model = BigAutoModel
    rel_db_type_class = models.BigIntegerField


class SmallAutoFieldTests(SmallIntegerFieldTests):
    model = SmallAutoModel
    rel_db_type_class = models.SmallIntegerField


class AutoFieldInheritanceTests(SimpleTestCase):

    def test_isinstance_of_autofield(self):
        for field in (models.BigAutoField, models.SmallAutoField):
            with self.subTest(field.__name__):
                self.assertIsInstance(field(), models.AutoField)

    def test_issubclass_of_autofield(self):
        for field in (models.BigAutoField, models.SmallAutoField):
            with self.subTest(field.__name__):
                self.assertTrue(issubclass(field, models.AutoField))

    def test_AUTOPK_001_direct_bigautofield_descendant_is_autofield_subclass(self):
        """AUTOPK-001: A direct BigAutoField descendant is an AutoField subclass."""
        class BigAutoFieldSubclass(models.BigAutoField):
            pass

        self.assertTrue(issubclass(BigAutoFieldSubclass, models.AutoField))

    def test_AUTOPK_001_indirect_bigautofield_descendant_is_autofield_subclass(self):
        """AUTOPK-001: An indirect BigAutoField descendant is an AutoField subclass."""
        class BigAutoFieldSubclass(models.BigAutoField):
            pass

        class BigAutoFieldSubclassSubclass(BigAutoFieldSubclass):
            pass

        self.assertTrue(issubclass(BigAutoFieldSubclassSubclass, models.AutoField))

    def test_AUTOPK_001_direct_smallautofield_descendant_is_autofield_subclass(self):
        """AUTOPK-001: A direct SmallAutoField descendant is an AutoField subclass."""
        class SmallAutoFieldSubclass(models.SmallAutoField):
            pass

        self.assertTrue(issubclass(SmallAutoFieldSubclass, models.AutoField))

    def test_AUTOPK_001_indirect_smallautofield_descendant_is_autofield_subclass(self):
        """AUTOPK-001: An indirect SmallAutoField descendant is an AutoField subclass."""
        class SmallAutoFieldSubclass(models.SmallAutoField):
            pass

        class SmallAutoFieldSubclassSubclass(SmallAutoFieldSubclass):
            pass

        self.assertTrue(issubclass(SmallAutoFieldSubclassSubclass, models.AutoField))
