from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("migrations", "0001_initial")]

    operations = [
        migrations.RenameIndex(
            model_name="book",
            new_name="book_idx",
            old_fields=("author", "title"),
        ),
    ]
