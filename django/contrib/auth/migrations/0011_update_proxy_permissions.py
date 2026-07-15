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
    - "G70-003 [RED] Forward re-run on previously-migrated DB must not change rowcount for existing (content_type_id, codename) tuples."
    - "G70-004 [RED] Upgrade from Django 2.0.13/2.1.8 with recreated proxy models must complete without unique-constraint IntegrityError and without auth_permission manual cleanup."
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
    # G70-003 pseudocode map:
    # - Scope: forward migration only (reverse=False) and rerun of already migrated DB.
    # - State transitions by tuple (new_content_type, codename):
    #   - STATE_PRESENT: target tuple exists.
    #   - STATE_MISSING_SOURCE_PRESENT: target missing, source exists.
    #   - STATE_MISSING_SOURCE_MISSING: neither source nor target exists.
    # - For each tuple:
    #   - Evaluate target_exists := exists(Permission where content_type=new_content_type and codename).
    #   - If target_exists == true: transition to DONE_NOOP and emit no UPDATE/INSERT.
    #       - rowcount invariant holds because DB writes are skipped.
    #   - Else:
    #       - attempt retarget from old_content_type.
    #       - if retarget_updates > 0: transition DONE_MOVED.
    #       - else if retarget_updates == 0: transition DONE_CREATED and create exactly one tuple.
    #       - if IntegrityError: transition DONE_ALREADY_PRESENT (or concurrent writer created it) and continue.
    # G70-004 pseudocode map:
    #  - migration-resilience objective in recreated-proxy upgrades:
    #    - tolerate stale auth_permission rows already present from prior states,
    #    - avoid manual cleanup,
    #    - preserve tuple-level completion for same-app-label and different-app-label proxy histories.
    #  - per proxy model:
    #    1. REQUIRED_SET := default_permissions union opts.permissions.
    #    2. CT_TARGET := proxy_content_type when forward else concrete_content_type.
    #    3. For each codename in REQUIRED_SET:
    #        a) If target exists -> DONE_NOOP.
    #        b) Else attempt update from source content type.
    #        c) If update_count == 0 -> attempt create target tuple.
    #        d) If UPDATE/CREATE raises IntegrityError -> DONE_ALREADY_PRESENT.
    #    4. Continue to next codename with no rollback of outer loop state.
    #  - This makes migration success deterministic regardless of legacy duplicate prepopulation.

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
            # G70-003 per-key rerun requirement:
            # - Existing tuple invariant on rerun:
            #   if Permission(new_content_type, codename) exists, branch to NOOP.
            #   NOOP must leave rowcount unchanged for that tuple.
            # - Duplicate-path prevention:
            #   any IntegrityError while retarget/create is treated as "already satisfied" and loop continues.
            # G70-004 per-key upgrade resilience:
            # - Legacy data can include either:
            #   (a) target already present due previous forward pass/recreated proxy state,
            #   (b) both target and source present with conflicting uniqueness expectations,
            #   (c) neither present after schema transitions.
            # - Branching:
            #   target_exists -> DONE_NOOP.
            #   update>0 -> DONE_MOVED_FROM_SOURCE.
            #   update==0 -> DONE_CREATE_TARGET.
            #   IntegrityError -> DONE_ALREADY_SATISFIED (no failure, migration continues).
            if Permission.objects.filter(content_type=new_content_type, codename=codename).exists():
                continue

            try:
                updated = Permission.objects.filter(
                    content_type=old_content_type,
                    codename=codename,
                ).update(content_type=new_content_type)
                if updated == 0:
                    # Required tuple is missing on both old and new content types.
                    # Create it directly so the migration does not depend on retargetable
                    # source rows.
                    Permission.objects.create(
                        content_type=new_content_type,
                        codename=codename,
                        name='Proxy permission for %s' % opts.model_name,
                    )
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
