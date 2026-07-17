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
            ],
            options={"index_together": {("author", "title")}},
        ),
        migrations.CreateModel(
            name="Publisher",
            fields=[("id", models.AutoField(primary_key=True))],
        ),
    ]
