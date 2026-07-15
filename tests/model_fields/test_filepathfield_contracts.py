import os
import shutil
import tempfile

from django.db import models
from django.test import SimpleTestCase

from .models import FilePathFieldCallablePathModel, get_local_upload_path


class FilePathFieldContractsFPF001Tests(SimpleTestCase):
    """
    FPF-001 mapping:
    - test_FPF_001_model_definition_preserves_callable_path_metadata
      -> model definition stores callable `path` on FilePathField without string coercion.
    - test_FPF_001_import_phase_has_no_eager_callable_path_filesystem_resolution
      -> import-time field registration does not materialize callable return value.
    """

    def test_FPF_001_model_definition_preserves_callable_path_metadata(self):
        """FPF-001: path callable remains attached to the field as object state."""
        field = FilePathFieldCallablePathModel._meta.get_field("file")
        self.assertIs(field.path, get_local_upload_path)
        self.assertNotIsInstance(field.path, str)
        self.assertTrue(callable(field.path))

    def test_FPF_001_import_phase_has_no_eager_callable_path_filesystem_resolution(self):
        """FPF-001: callable `path` is not eagerly resolved during import-time registration."""
        call_count = []

        temp_dir = tempfile.mkdtemp()

        def get_local_upload_path():
            call_count.append(1)
            return temp_dir

        class FilePathFieldCallablePathImportModel(models.Model):
            file = models.FilePathField(path=get_local_upload_path)

            class Meta:
                app_label = "model_fields"

        field = FilePathFieldCallablePathImportModel._meta.get_field("file")
        self.assertEqual(call_count, [])
        self.assertIs(field.path, get_local_upload_path)
        self.assertTrue(callable(field.path))

        field.formfield()
        self.assertEqual(len(call_count), 1)
        shutil.rmtree(temp_dir)


FPF_003_VERIFICATION_MAP = {
    "FPF-003": [
        "test_FPF_003_runtime_callable_invocation_uses_current_host_path_for_choice_enumeration",
        "test_FPF_003_host_locality_choices_observe_current_runtime_path_output",
    ],
}

FPF_004_VERIFICATION_MAP = {
    "FPF-004": [
        "test_FPF_004_string_path_runtime_choices_match_legacy_current_behavior",
        "test_FPF_004_string_and_callable_path_runtime_choices_share_semantics_contract",
    ],
}

FPF_007_VERIFICATION_MAP = {
    "FPF-007": [
        "test_FPF_007_parity_between_string_and_callable_paths_for_match_recursive_allow_files_and_allow_folders",
        "test_FPF_007_recursive_false_immediate_folders_only_with_allow_folders_true_allow_files_false_preserved_across_path_forms",
    ],
}


class FilePathFieldContractsFPF003Tests(SimpleTestCase):
    """
    FPF-003 mapping:
    - test_FPF_003_runtime_callable_invocation_uses_current_host_path_for_choice_enumeration
      -> canonical requirement: callable `path` executes at runtime during path-based enumeration.
    - test_FPF_003_host_locality_choices_observe_current_runtime_path_output
      -> canonical requirement: different hosts can observe different directory contents by callable output.
    """

    def test_FPF_003_runtime_callable_invocation_uses_current_host_path_for_choice_enumeration(self):
        """FPF-003 Scenario 1: evaluate callable path in host runtime when choices are requested."""
        with tempfile.TemporaryDirectory() as host_a_dir, tempfile.TemporaryDirectory() as host_b_dir:
            alpha_file = os.path.join(host_a_dir, "alpha.txt")
            beta_file = os.path.join(host_b_dir, "beta.txt")
            with open(alpha_file, "w"):
                pass
            with open(beta_file, "w"):
                pass

            calls = []

            def get_host_path():
                path = host_a_dir if not calls else host_b_dir
                calls.append(path)
                return path

            class FilePathFieldRuntimeCallableModel(models.Model):
                file = models.FilePathField(path=get_host_path)

                class Meta:
                    app_label = "model_fields"

            field = FilePathFieldRuntimeCallableModel._meta.get_field("file")

            form_field = field.formfield()
            self.assertEqual(calls, [host_a_dir])
            self.assertIn((alpha_file, os.path.basename(alpha_file)), form_field.choices)
            self.assertNotIn((beta_file, os.path.basename(beta_file)), form_field.choices)

            form_field = field.formfield()
            self.assertEqual(calls, [host_a_dir, host_b_dir])
            self.assertIn((beta_file, os.path.basename(beta_file)), form_field.choices)
            self.assertNotIn((alpha_file, os.path.basename(alpha_file)), form_field.choices)

    def test_FPF_003_host_locality_choices_observe_current_runtime_path_output(self):
        """FPF-003 Scenario 2: enumeration reflects host-local callable output."""
        with tempfile.TemporaryDirectory() as host_one_root, tempfile.TemporaryDirectory() as host_two_root:
            host_one_file = os.path.join(host_one_root, "host-one.txt")
            host_two_file = os.path.join(host_two_root, "host-two.txt")
            with open(host_one_file, "w"):
                pass
            with open(host_two_file, "w"):
                pass

            runtime_state = {"host_root": host_one_root}

            def get_host_path():
                return runtime_state["host_root"]

            class FilePathFieldRuntimeHostLocalModel(models.Model):
                file = models.FilePathField(path=get_host_path)

                class Meta:
                    app_label = "model_fields"

            field = FilePathFieldRuntimeHostLocalModel._meta.get_field("file")

            runtime_state["host_root"] = host_one_root
            first_form_field = field.formfield()
            self.assertIn((host_one_file, os.path.basename(host_one_file)), first_form_field.choices)
            self.assertNotIn((host_two_file, os.path.basename(host_two_file)), first_form_field.choices)

            runtime_state["host_root"] = host_two_root
            second_form_field = field.formfield()
            self.assertIn((host_two_file, os.path.basename(host_two_file)), second_form_field.choices)
            self.assertNotIn((host_one_file, os.path.basename(host_one_file)), second_form_field.choices)


class FilePathFieldContractsFPF004Tests(SimpleTestCase):
    """FPF-004 runtime-locus traceability placeholders."""

    def test_FPF_004_string_path_runtime_choices_match_legacy_current_behavior(self):
        """FPF-004 Scenario 2: string and callable path runtime choice behavior remains traceable."""
        with tempfile.TemporaryDirectory() as path_root:
            allowed_file = os.path.join(path_root, "allowed.txt")
            blocked_file = os.path.join(path_root, "blocked.tmp")
            with open(allowed_file, "w"), open(blocked_file, "w"):
                pass

            with open(os.path.join(path_root, "__pycache__"), "w"):
                pass

            class FilePathFieldRuntimeStringPathModel(models.Model):
                file = models.FilePathField(path=path_root, match=r"^.*\\.txt$")

                class Meta:
                    app_label = "model_fields"

            field = FilePathFieldRuntimeStringPathModel._meta.get_field("file")
            form_field = field.formfield()

            self.assertIn((allowed_file, os.path.basename(allowed_file)), form_field.choices)
            self.assertNotIn((blocked_file, os.path.basename(blocked_file)), form_field.choices)
            self.assertNotIn(
                (os.path.join(path_root, "__pycache__"), os.path.basename("__pycache__")),
                form_field.choices,
            )

    def test_FPF_004_string_and_callable_path_runtime_choices_share_semantics_contract(self):
        """FPF-004 Scenario 2: baseline parity contract across string vs callable path models."""
        with tempfile.TemporaryDirectory() as path_root:
            alpha = os.path.join(path_root, "alpha.txt")
            with open(alpha, "w"):
                pass

            def get_root_path():
                return path_root

            class FilePathFieldRuntimeStringPathModel(models.Model):
                file = models.FilePathField(path=path_root)

                class Meta:
                    app_label = "model_fields"

            class FilePathFieldRuntimeCallablePathModel(models.Model):
                file = models.FilePathField(path=get_root_path)

                class Meta:
                    app_label = "model_fields"

            string_field = FilePathFieldRuntimeStringPathModel._meta.get_field("file")
            callable_field = FilePathFieldRuntimeCallablePathModel._meta.get_field("file")

            self.assertEqual(
                string_field.formfield().choices,
                callable_field.formfield().choices,
            )


class FilePathFieldContractsFPF007Tests(SimpleTestCase):
    """FPF-007 mapping:
    - test_FPF_007_parity_between_string_and_callable_paths_for_match_recursive_allow_files_and_allow_folders
      -> canonical requirement: all option flags preserve identical filtering for callable and string path forms.
    - test_FPF_007_recursive_false_immediate_folders_only_with_allow_folders_true_allow_files_false_preserved_across_path_forms
      -> canonical requirement: nested/edge flag behavior for non-recursive folder-only enumeration.
    """

    def test_FPF_007_parity_between_string_and_callable_paths_for_match_recursive_allow_files_and_allow_folders(self):
        """FPF-007 Scenario 1: options parity for callable vs string path."""
        with tempfile.TemporaryDirectory() as path_root:
            nested_a = os.path.join(path_root, "nested_a")
            nested_b = os.path.join(path_root, "nested_b")
            nested_a_inner = os.path.join(nested_a, "inner")
            nested_b_inner = os.path.join(nested_b, "inner")
            pycache_dir = os.path.join(path_root, "__pycache__")
            pycache_file = os.path.join(pycache_dir, "cache.txt")
            os.makedirs(nested_a_inner)
            os.makedirs(nested_b_inner)
            os.makedirs(pycache_dir)

            root_txt = os.path.join(path_root, "root.txt")
            root_py = os.path.join(path_root, "root.py")
            root_md = os.path.join(path_root, "root.md")
            nested_a_txt = os.path.join(nested_a, "nested_a.txt")
            nested_a_py = os.path.join(nested_a, "nested_a.py")
            nested_b_txt = os.path.join(nested_b, "nested_b.txt")
            nested_b_py = os.path.join(nested_b, "nested_b.py")
            nested_a_inner_txt = os.path.join(nested_a_inner, "nested_a_inner.txt")
            nested_b_inner_txt = os.path.join(nested_b_inner, "nested_b_inner.txt")
            with open(root_txt, "w"), open(root_py, "w"), open(root_md, "w"):
                pass
            with open(nested_a_txt, "w"), open(nested_a_py, "w"), open(nested_b_txt, "w"), open(nested_b_py, "w"):
                pass
            with open(nested_a_inner_txt, "w"), open(nested_b_inner_txt, "w"), open(pycache_file, "w"):
                pass

            expected = [
                (root_txt, "root.txt"),
                (nested_a_txt, "nested_a/nested_a.txt"),
                (nested_b_txt, "nested_b/nested_b.txt"),
                (nested_a_inner_txt, "nested_a/inner/nested_a_inner.txt"),
                (nested_b_inner_txt, "nested_b/inner/nested_b_inner.txt"),
            ]

            def get_root_path():
                return path_root

            class FilePathFieldStringPathFPF007Model(models.Model):
                file = models.FilePathField(
                    path=path_root,
                    match=r"^.*\.txt$",
                    recursive=True,
                    allow_files=True,
                    allow_folders=False,
                )

                class Meta:
                    app_label = "model_fields"

            class FilePathFieldCallablePathFPF007Model(models.Model):
                file = models.FilePathField(
                    path=get_root_path,
                    match=r"^.*\.txt$",
                    recursive=True,
                    allow_files=True,
                    allow_folders=False,
                )

                class Meta:
                    app_label = "model_fields"

            string_field = FilePathFieldStringPathFPF007Model._meta.get_field("file")
            callable_field = FilePathFieldCallablePathFPF007Model._meta.get_field("file")
            self.assertEqual(string_field.formfield().choices, expected)
            self.assertEqual(callable_field.formfield().choices, expected)
            self.assertEqual(string_field.formfield().choices, callable_field.formfield().choices)

    def test_FPF_007_recursive_false_immediate_folders_only_with_allow_folders_true_allow_files_false_preserved_across_path_forms(self):
        """FPF-007 Scenario 2: non-recursive folder-only filtering remains identical for both path forms."""
        with tempfile.TemporaryDirectory() as path_root:
            immediate_folder_a = os.path.join(path_root, "alpha")
            immediate_folder_b = os.path.join(path_root, "bravo")
            nested_folder = os.path.join(path_root, "alpha", "nested")
            pycache_dir = os.path.join(path_root, "__pycache__")
            os.makedirs(nested_folder)
            os.makedirs(pycache_dir)

            with open(os.path.join(path_root, "file.txt"), "w"), open(os.path.join(path_root, "another.bin"), "w"):
                pass
            with open(os.path.join(immediate_folder_a, "a.txt"), "w"), open(os.path.join(immediate_folder_b, "b.txt"), "w"):
                pass
            with open(os.path.join(pycache_dir, "bad.txt"), "w"):
                pass

            expected = [
                (os.path.join(path_root, "alpha"), "alpha"),
                (os.path.join(path_root, "bravo"), "bravo"),
            ]

            def get_root_path():
                return path_root

            class FilePathFieldStringPathImmediateFolderModel(models.Model):
                file = models.FilePathField(
                    path=path_root,
                    recursive=False,
                    allow_files=False,
                    allow_folders=True,
                )

                class Meta:
                    app_label = "model_fields"

            class FilePathFieldCallablePathImmediateFolderModel(models.Model):
                file = models.FilePathField(
                    path=get_root_path,
                    recursive=False,
                    allow_files=False,
                    allow_folders=True,
                )

                class Meta:
                    app_label = "model_fields"

            string_field = FilePathFieldStringPathImmediateFolderModel._meta.get_field("file")
            callable_field = FilePathFieldCallablePathImmediateFolderModel._meta.get_field("file")
            self.assertEqual(string_field.formfield().choices, expected)
            self.assertEqual(callable_field.formfield().choices, expected)
            self.assertEqual(string_field.formfield().choices, callable_field.formfield().choices)
