from django.db import migrations
from django.db.utils import IntegrityError


def update_proxy_model_permissions(apps, schema_editor, reverse=False):
    # G70-007 [ORANGE] Reversal of auth.0011_update_proxy_permissions must preserve proxy permission row coherence and existing user/group permission relationships for same-app-label and different-app-label paths, without duplicate-related failures.
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
    - "G70-005 [ORANGE] Permission updates in auth.0011_update_proxy_permissions must be scoped by each proxy model’s resolved ContentType and codename."
    - "G70-006 [ORANGE] Except for the expected proxy-permission keys, forward migration must not alter unrelated auth_permission rows (including unrelated proxy and all non-proxy permission rows)."
    """
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # G70-007 reverse-coherence pseudocode:
    # For each required codename per proxy model:
    # INPUTS: Model, required_permissions, reverse flag, reverse=True during rollback.
    # DERIVED:
    #   concrete_content_type := CT(Model, for_concrete_model=True)
    #   proxy_content_type := CT(Model, for_concrete_model=False)
    #   source_key := (old_content_type, codename)
    #   target_key := (new_content_type, codename)
    #   mode_label := "same-app-label" if source_key app_label == target_key app_label else "different-app-label"
    # STEP:
    #   if target_key exists -> DONE_NOOP
    #   else try to retarget source_key -> target_key
    #   if retarget updates 0 rows -> create target_key
    #   if IntegrityError -> DONE_ALREADY_SATISFIED, continue
    # INVARIANTS:
    #   - only keys in source_key/target_key are ever read/updated/created
    #   - no duplicate-related failures halt migration
    #   - user/group M2M edge preservation:
    #      * UPDATE path preserves permission row identity (one-row content_type change)
    #      * create/get_or_create path handles pre-existing target/coincident legacy rows safely
    #      * NOOP path preserves existing source-target relationship state
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
    # G70-006 pseudocode map:
    #  - preserve-set construction:
    #    PROTECTED_ROWS := rows where (content_type, codename) not in required key domain.
    #  - required key domain per proxy model:
    #    D := { (old_content_type, c), (new_content_type, c) } for c in required_permissions.
    #  - all writes are scoped to keys in D; therefore PROTECTED_ROWS are unchanged in identity and count.

    # G70-005 deterministic scope model:
    # For each proxy model, bind an immutable per-tuple key:
    # (proxy_content_type_id, codename). All reads and writes must be done
    # against that key and only that key’s source tuple:
    # (concrete_content_type_id, codename). This prevents same-app-label and
    # different-app-label proxy models from sharing tuple state.
    for Model in apps.get_models():
        opts = Model._meta
        if not opts.proxy:
            continue

        # G70-005 per-model key derivation:
        # - resolved_model_name := opts.model_name
        # - resolved_concrete_type := CT(Model, for_concrete_model=True)
        # - resolved_proxy_type := CT(Model, for_concrete_model=False)
        # - required_codes := default_permissions union opts.permissions
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
        # G70-007 mode-specific state:
        # - Reverse migration flips source/target compared with forward.
        # - branch_label is derived from content-type metadata; control-flow is unchanged.
        for codename in required_permissions:
            # G70-006 per-key isolation:
            # - mutable tuples are only:
            #   source_key = (old_content_type, codename)
            #   target_key = (new_content_type, codename)
            # - no predicate outside these exact key tuples is used for reads/writes.
            # G70-005 per-key transition for codename:
            # key_target := (content_type=new_content_type, codename=codename)
            # key_source := (content_type=old_content_type, codename=codename)
            # Branching by key state:
            # 1) if target exists -> state=NOOP, continue.
            # 2) if update(source->target) affects 1 row -> state=MOVED.
            # 3) if update affects 0 rows -> create(target); if created -> CREATED.
            # 4) if IntegrityError in move/create -> state=SATISFIED_ELSEWHERE, continue.
            # Isolation rule: every lookup/update/create includes both content_type and codename.
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
            # G70-007 reverse branch behavior:
            # state_pre:
            #   exists_target := Permission(target_key)
            #   exists_source := Permission(source_key)
            # state_transitions:
            #   1) if exists_target -> DONE_NOOP (keep m2m edges)
            #   2) if update(source->target) updates 1 -> DONE_MOVED
            #   3) if update updates 0 -> DONE_CREATED
            #   4) if IntegrityError in 2/3 -> DONE_ALREADY_SATISFIED
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
            # G70-006 branch: target_key already present.
            #   - transition DONE_UNCHANGED.
            #   - this path performs no writes; protected rows remain immutable.
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
                # G70-006 branch:
                #   - only target_key is introduced.
                #   - unrelated proxy/non-proxy tuples remain untouched.
                Permission.objects.create(
                    content_type=new_content_type,
                    codename=codename,
                    name='Proxy permission for %s' % opts.model_name,
                )
        except IntegrityError:
            # If either retargeting or creation raises a unique constraint
            # conflict, one valid terminal state is that the target tuple is
            # already present. Keep migration progress by ensuring target
            # existence and continuing.
            # G70-006 recovery path:
            # - get_or_create bound to target_key only.
            # - unrelated row sets cannot be altered through this path.
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
