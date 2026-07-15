from django.db import migrations
from django.db.utils import IntegrityError


def update_proxy_model_permissions(apps, schema_editor, reverse=False):
    """
    Update the content_type of proxy model permissions to use the content_type of the
    proxy model.
    """
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    for Model in apps.get_models():
        opts = Model._meta
        if not opts.proxy:
            continue

        required_permissions = {
            '%s_%s' % (action, opts.model_name)
            for action in opts.default_permissions
        }
        for codename, _name in opts.permissions:
            required_permissions.add(codename)

        concrete_content_type = ContentType.objects.get_for_model(Model, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Model, for_concrete_model=False)
        old_content_type = proxy_content_type if reverse else concrete_content_type
        new_content_type = concrete_content_type if reverse else proxy_content_type

        for codename in required_permissions:
            if Permission.objects.filter(content_type=new_content_type, codename=codename).exists():
                print(
                    "A problem arose migrating proxy model permissions: "
                    "permission %r for %r already exists, skipping." % (
                        codename,
                        opts.label,
                    )
                )
                continue
            try:
                updated = Permission.objects.filter(
                    content_type=old_content_type,
                    codename=codename,
                ).update(content_type=new_content_type)
                if updated == 0:
                    Permission.objects.create(
                        content_type=new_content_type,
                        codename=codename,
                        name='Proxy permission for %s' % opts.model_name,
                    )
            except IntegrityError:
                print(
                    "A problem arose migrating proxy model permissions: "
                    "permission %r for %r already exists." % (
                        codename,
                        opts.label,
                    )
                )
                Permission.objects.get_or_create(
                    content_type=new_content_type,
                    codename=codename,
                    defaults={
                        'name': 'Proxy permission for %s' % opts.model_name,
                    },
                )


def revert_proxy_model_permissions(apps, schema_editor):
    """
    Update the content_type of proxy model permissions to use the ContentType
    of the concrete model.
    """
    update_proxy_model_permissions(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0010_alter_group_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]
    operations = [
        migrations.RunPython(update_proxy_model_permissions, revert_proxy_model_permissions),
    ]
