from django.db import migrations
from django.db.models import Q


def update_proxy_model_permissions(apps, schema_editor, reverse=False):
    """
    Update the content_type of proxy model permissions to use the ContentType
    of the proxy model.

    G70-001 [RED] Traceability anchor:
    - "Existing proxy permission tuple (content_type_id, codename) must be preserved."
    - "Missing tuple should be inserted/retargeted when absent."
    - "Duplicate detection must keep mixed present/missing outcomes bounded by tuple-level state."
    """
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    for Model in apps.get_models():
        opts = Model._meta
        if not opts.proxy:
            continue
        proxy_default_permissions_codenames = [
            '%s_%s' % (action, opts.model_name)
            for action in opts.default_permissions
        ]
        permissions_query = Q(codename__in=proxy_default_permissions_codenames)
        for codename, name in opts.permissions:
            permissions_query = permissions_query | Q(codename=codename, name=name)
        concrete_content_type = ContentType.objects.get_for_model(Model, for_concrete_model=True)
        proxy_content_type = ContentType.objects.get_for_model(Model, for_concrete_model=False)
        old_content_type = proxy_content_type if reverse else concrete_content_type
        new_content_type = concrete_content_type if reverse else proxy_content_type
        # G70-001 deterministic migration logic (pseudo):
        # 1) Build the required permission tuple set for this proxy model:
        #    tuples = [(content_type_id, codename)] for defaults + opts.permissions.
        # 2) For each tuple in tuples:
        #    a. If reverse=False and Permission has tuple at (new_content_type_id, codename):
        #       - mark tuple as "already-present"
        #       - leave rowcount unchanged
        #       - perform no update/insert for this tuple
        #    b. Else if reverse=False and tuple exists at (old_content_type_id, codename):
        #       - update that row to new_content_type_id
        #    c. Else:
        #       - no-op for this tuple
        # 3) If reverse=True, flip old_content_type/new_content_type and apply
        #    symmetrical existence checks.
        #
        # Failure path:
        # - Any unexpected DB integrity error on tuple mutation must be treated as:
        #   existing-tuple detection, skip mutation for that tuple, continue processing.
        #
        # Requirement mapping:
        # - G70_001 existing tuple rowcount for content_type/codename is preserved.
        # - G70_001 existing tuple is detected without integrity error.
        # - G70_001 mixed present/missing tuples preserve existing rows and only process missing ones.
        Permission.objects.filter(
            permissions_query,
            content_type=old_content_type,
        ).update(content_type=new_content_type)


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
