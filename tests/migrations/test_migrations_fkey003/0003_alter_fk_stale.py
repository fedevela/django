from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("migrations", "0002_rename_pk"),
    ]

    operations = [
        migrations.AlterField(
            model_name="Book",
            name="anchor",
            field=models.ForeignKey("migrations.Anchor", models.CASCADE, to_field="field_wrong"),
        ),
    ]
