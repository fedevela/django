from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    operations = [
        migrations.CreateModel(
            "Anchor",
            [
                ("field_wrong", models.AutoField(primary_key=True)),
            ],
        ),
        migrations.CreateModel(
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                (
                    "anchor",
                    models.ForeignKey(
                        "migrations.Anchor",
                        models.CASCADE,
                        to_field="field_wrong",
                    ),
                ),
            ],
        ),
    ]
