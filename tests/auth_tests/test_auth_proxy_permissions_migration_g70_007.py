from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from .models import Proxy, UserProxy


update_proxy_permissions = import_module(
    'django.contrib.auth.migrations.0011_update_proxy_permissions'
)


G70_007_REQUIREMENT_TO_VERIFICATION = {
    "G70-007": [
        "G70_007UpdateProxyPermissionsTraceabilityTests::test_G70_007_reversal_of_auth_0011_preserves_proxy_permission_row_coherence_without_duplicate_related_failures",
        "G70_007UpdateProxyPermissionsTraceabilityTests::test_G70_007_reversal_preserves_user_and_group_proxy_permission_relationships_in_same_app_label_mode",
        "G70_007UpdateProxyPermissionsTraceabilityTests::test_G70_007_reversal_preserves_user_and_group_proxy_permission_relationships_in_different_app_label_mode",
    ],
}


class G70_007UpdateProxyPermissionsTraceabilityTests(TestCase):
    # G70-007 requirement-to-logic map:
    # - Reverse coherence:
    #   input: affected proxy and concrete permission tuples after forward migration.
    #   process: execute revert path for each required codename.
    #   output: tuple is in coherent terminal state (existing target/no new duplicate).
    # - Relationship preservation:
    #   input: existing auth_user_user_permissions / auth_group_permissions rows for affected permissions.
    #   process: rollback branch preserves valid permission row identity or stabilizes target with get_or_create.
    #   output: user/group relationship sets remain coherent and no IntegrityError aborts.
    available_apps = [
        "auth_tests",
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]

    def setUp(self):
        Permission.objects.all().delete()
        User.objects.all().delete()
        Group.objects.all().delete()

    def _content_types(self, model):
        return (
            ContentType.objects.get_for_model(model, for_concrete_model=True),
            ContentType.objects.get_for_model(model, for_concrete_model=False),
        )

    def test_G70_007_reversal_of_auth_0011_preserves_proxy_permission_row_coherence_without_duplicate_related_failures(self):
        concrete_content_type, proxy_content_type = self._content_types(Proxy)

        # G70-007 reverse coherence pseudocode:
        # 1) identify affected proxy models and required permission codenames
        # 2) seed mixed pre-revert states (target-only, source-only, both-missing, both-present)
        # 3) call revert path
        # 4) assert per codename state transition:
        #    - target present -> DONE_NOOP
        #    - moved -> DONE_MOVED
        #    - created -> DONE_CREATED
        #    - collision -> DONE_ALREADY_SATISFIED (no failure)
        source_only_codename = "add_proxy"
        target_only_codename = "change_proxy"
        missing_codename = "delete_proxy"
        collision_codename = "display_proxys"

        source_only_permission = Permission.objects.create(
            content_type=proxy_content_type,
            codename=source_only_codename,
            name="Source row should be moved",
        )
        Permission.objects.create(
            content_type=concrete_content_type,
            codename=target_only_codename,
            name="Target row already present",
        )
        Permission.objects.create(
            content_type=concrete_content_type,
            codename=collision_codename,
            name="Existing target collision row",
        )
        Permission.objects.create(
            content_type=proxy_content_type,
            codename=collision_codename,
            name="Source collision row",
        )

        update_proxy_permissions.revert_proxy_model_permissions(apps, None)

        moved_permission = Permission.objects.get(
            content_type=concrete_content_type,
            codename=source_only_codename,
        )
        missing_permission = Permission.objects.get(
            content_type=concrete_content_type,
            codename=missing_codename,
        )

        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=source_only_codename,
            ).count(),
            0,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_content_type,
                codename=target_only_codename,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_content_type,
                codename=missing_codename,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=missing_codename,
            ).count(),
            0,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_content_type,
                codename=collision_codename,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=collision_codename,
            ).count(),
            1,
        )
        self.assertEqual(moved_permission.id, source_only_permission.id)
        self.assertEqual(moved_permission.name, source_only_permission.name)
        self.assertEqual(missing_permission.name, 'Proxy permission for proxy')

    def test_G70_007_reversal_preserves_user_and_group_proxy_permission_relationships_in_same_app_label_mode(self):
        # G70-007 relationship logic pseudocode for same-app-label mode:
        # 1) create proxy permissions and related user/group permission links where
        #    app_label(source) == app_label(target)
        # 2) execute rollback for the same model pair repeatedly if needed
        # 3) verify:
        #    - user/group FK rows remain valid
        #    - permissions referenced by links still satisfy lookup via has_perm-style codename checks
        concrete_content_type, proxy_content_type = self._content_types(Proxy)
        codename = "add_proxy"
        source_permission = Permission.objects.create(
            content_type=proxy_content_type,
            codename=codename,
            name="Coherent same-app permission",
        )

        user = User.objects.create()
        group = Group.objects.create(name="same-app-group")
        user.user_permissions.add(source_permission)
        group.permissions.add(source_permission)

        update_proxy_permissions.revert_proxy_model_permissions(apps, None)

        target_permission = Permission.objects.get(
            content_type=concrete_content_type,
            codename=codename,
        )
        user = User.objects.get(pk=user.pk)
        group = Group.objects.get(pk=group.pk)

        self.assertTrue(user.has_perm("auth_tests.add_proxy"))
        self.assertTrue(
            user.user_permissions.filter(pk=target_permission.pk).exists(),
        )
        self.assertFalse(
            user.user_permissions.filter(pk=source_permission.pk).exists(),
        )
        self.assertTrue(
            group.permissions.filter(pk=target_permission.pk).exists(),
        )
        self.assertFalse(
            group.permissions.filter(pk=source_permission.pk).exists(),
        )
        self.assertEqual(target_permission.id, source_permission.id)

    def test_G70_007_reversal_preserves_user_and_group_proxy_permission_relationships_in_different_app_label_mode(self):
        # G70-007 relationship logic pseudocode for different-app-label mode:
        # 1) create source/target permission tuples with differing app labels
        # 2) attach users/groups to source-side permissions
        # 3) run rollback path
        # 4) verify:
        #    - no duplicate-related IntegrityError path
        #    - related users/groups resolve to a coherent permission identity in either source/target state
        concrete_content_type, proxy_content_type = self._content_types(UserProxy)
        moved_codename = "use_different_app_label"
        colliding_codename = "add_userproxy"

        moved_source_permission = Permission.objects.create(
            content_type=proxy_content_type,
            codename=moved_codename,
            name="Move path source permission",
        )
        collision_source_permission = Permission.objects.create(
            content_type=proxy_content_type,
            codename=colliding_codename,
            name="Pre-existing source collision",
        )
        collision_target_permission = Permission.objects.create(
            content_type=concrete_content_type,
            codename=colliding_codename,
            name="Pre-existing target collision",
        )

        user = User.objects.create()
        group = Group.objects.create(name="different-app-group")
        user.user_permissions.add(moved_source_permission, collision_source_permission)
        group.permissions.add(collision_target_permission)

        update_proxy_permissions.revert_proxy_model_permissions(apps, None)

        user = User.objects.get(pk=user.pk)
        group = Group.objects.get(pk=group.pk)
        moved_target_permission = Permission.objects.get(
            content_type=concrete_content_type,
            codename=moved_codename,
        )

        self.assertTrue(user.has_perm("auth.use_different_app_label"))
        self.assertFalse(user.has_perm("auth_tests.use_different_app_label"))
        self.assertTrue(
            user.user_permissions.filter(pk=moved_target_permission.pk).exists(),
        )
        self.assertEqual(
            user.user_permissions.filter(pk=collision_source_permission.pk).count(),
            1,
        )
        self.assertTrue(
            group.permissions.filter(pk=collision_target_permission.pk).exists(),
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=concrete_content_type,
                codename=colliding_codename,
            ).count(),
            1,
        )
        self.assertEqual(
            Permission.objects.filter(
                content_type=proxy_content_type,
                codename=colliding_codename,
            ).count(),
            1,
        )
