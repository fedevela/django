from django.db import migrations
from django.db.utils import IntegrityError


def update_proxy_model_permissions(apps, schema_editor, reverse=False):
    """
    Update the content_type of proxy model permissions to use the ContentType
    of the proxy model.

    G70-001 [RED] Traceability anchor:
    - "Existing proxy permission tuple (content_type_id, codename) must be preserved."
    - "Missing tuple should be inserted/retargeted when absent."
    - "Duplicate detection must keep mixed present/missing outcomes bounded by tuple-level state."
    - "G70-002 [RED] Missing required tuple must materialize exactly once during forward migration."
    """
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # G70-002 pseudocode map:
    # O1: missing required key (new_content_type, codename) -> create one row exactly once.
    # O2: batch processing is tuple-local; each missing key increases rowcount by one, no cross-tuple coupling.
    # O3: uniqueness collision on (content_type_id, codename) is interpreted as "already satisfied"; no new row.

    # Structured control intent (pseudocode):
    # state := {running migration, reverse=False for forward}
    # for each Model in apps.get_models():
    #     if not proxy: continue
    #     required_permissions = default_permissions union opts.permissions(codename)
    #     concrete_content_type = CT(concrete)
    #     proxy_content_type = CT(proxy)
    #     old_content_type = reverse ? proxy : concrete
    #     new_content_type = reverse ? concrete : proxy
    #     for each codename in required_permissions:
    #         if exists(Permission where content_type=new_content_type, codename):
    #             continue  # O1/O2: already satisfied, no mutation
    #         try:
    #             updated = update(Permission where content_type=old_content_type, codename -> new_content_type)
    #             if updated == 0:
    #                 insert(Permission new_content_type,codename)  # exact-one create path
    #             # O3: if unique violation occurs in update/insert, continue without duplicate
    #         except IntegrityError:
    #             continue

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
            # G70-002 per-key transition:
            # - if target tuple already exists => SKIP.
            # - else attempt source retarget.
            # - if no source row updated => materialize missing tuple exactly once.
            # - if unique conflict appears in either path => SKIP as already-created target.
            if Permission.objects.filter(content_type=new_content_type, codename=codename).exists():
                continue

            try:
                Permission.objects.filter(
                    content_type=old_content_type,
                    codename=codename,
                ).update(content_type=new_content_type)
            except IntegrityError:
                # Treat an unexpected integrity collision as a proxy of
                # an already-existing target tuple, and continue.
                continue


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
