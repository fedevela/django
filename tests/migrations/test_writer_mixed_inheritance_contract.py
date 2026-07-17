from django.db import migrations, models
from django.db.migrations.writer import MigrationWriter
from django.test import SimpleTestCase

from migration_writer_app.models import MyField, MyMixin


class MixedModelInheritanceMigrationContractTests(SimpleTestCase):
    def migration_source(self):
        migration = type("Migration", (migrations.Migration,), {
            "operations": [
                migrations.CreateModel(
                    name="MyModel",
                    fields=[
                        ("id", MyField(primary_key=True, serialize=False)),
                    ],
                    options={"abstract": False},
                    bases=(MyMixin, models.Model),
                ),
            ],
            "dependencies": [],
        })
        return MigrationWriter(migration, include_header=False).as_string()

    def test_MIG_001_models_model_reference_has_resolving_import(self):
        """GUID: MIG-001 - models.Model has a resolving import."""
        source = self.migration_source()
        self.assertIn("from django.db import migrations, models\n", source)

    def test_MIG_002_generated_migration_loads_without_reference_name_error(self):
        """GUID: MIG-002 - emitted references load without NameError."""
        namespace = {}
        exec(self.migration_source(), namespace)
        self.assertIn("Migration", namespace)

    def test_MIG_003_create_model_preserves_mixin_and_models_model_bases(self):
        """GUID: MIG-003 - bases remain (app.models.MyMixin, models.Model)."""
        source = self.migration_source()
        module = MyMixin.__module__
        self.assertIn("bases=(%s.MyMixin, models.Model)," % module, source)

    def test_MIG_004_create_model_preserves_custom_primary_key_field(self):
        """GUID: MIG-004 - MyField remains primary_key=True, serialize=False."""
        source = self.migration_source()
        module = MyField.__module__
        self.assertIn(
            "('id', %s.MyField(primary_key=True, serialize=False))," % module,
            source,
        )

    def test_MIG_005_create_model_preserves_abstract_false_option(self):
        """GUID: MIG-005 - CreateModel preserves abstract=False."""
        self.assertIn("'abstract': False,", self.migration_source())

    def test_MIG_006_generated_migration_retains_app_models_import(self):
        """GUID: MIG-006 - app.models remains imported for the mixin and field."""
        module = MyMixin.__module__
        self.assertIn("import %s\n" % module, self.migration_source())

    def test_MIG_007_migration_without_models_reference_omits_models_import(self):
        """GUID: MIG-007 - no models.* reference means no added models import."""
        migration = type("Migration", (migrations.Migration,), {
            "operations": [
                migrations.AlterModelOptions(
                    name="MyModel",
                    options={"verbose_name": "My model"},
                ),
            ],
            "dependencies": [],
        })
        source = MigrationWriter(migration, include_header=False).as_string()
        self.assertIn("from django.db import migrations\n", source)
        self.assertNotIn("from django.db import migrations, models\n", source)

    def test_MIG_008_mixed_inheritance_regression_covers_models_import(self):
        """GUID: MIG-008 - regression coverage verifies the models.Model import."""
        source = self.migration_source()
        self.assertIn("models.Model", source)
        self.assertIn("from django.db import migrations, models", source)
