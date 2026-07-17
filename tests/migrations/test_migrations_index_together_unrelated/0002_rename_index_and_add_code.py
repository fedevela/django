from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("migrations", "0001_initial")]

    operations = [
        migrations.RenameIndex(
            model_name="book",
            new_name="book_idx",
            old_fields=("author", "title"),
        ),
        migrations.AddField(
            model_name="publisher",
            name="code",
            field=models.CharField(max_length=8, null=True),
        ),
    ]
