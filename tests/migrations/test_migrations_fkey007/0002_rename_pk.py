from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("migrations", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="Anchor",
            old_name="field_wrong",
            new_name="field_fixed",
        )
    ]
