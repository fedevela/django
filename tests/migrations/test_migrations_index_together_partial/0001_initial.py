from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    operations = [
        migrations.CreateModel(
            name="Book",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                ("author", models.CharField(max_length=255)),
                ("title", models.CharField(max_length=255)),
                ("isbn", models.CharField(max_length=13)),
            ],
            options={
                "index_together": {
                    ("author", "title"),
                    ("title", "isbn"),
                }
            },
        ),
    ]
