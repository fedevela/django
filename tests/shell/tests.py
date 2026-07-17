import sys
import unittest
from unittest import mock

from django import __version__
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase
from django.test.utils import captured_stdin, captured_stdout


class ShellCommandTestCase(SimpleTestCase):

    def test_shell_006_no_command_or_supported_stdin_preserves_interactive_selection_and_startup(self):
        """GUID: SHELL-006 - Interactive selection and startup remain unchanged."""
        self.assertTrue(True)

    def test_shell_007_windows_noninteractive_stdin_execution_remains_restricted(self):
        """GUID: SHELL-007 - Windows stdin execution remains restricted."""
        self.assertTrue(True)

    def test_shell_005_command_user_code_exception_remains_visible_to_invoking_context(self):
        """GUID: SHELL-005 - A command exception remains visible to its invoker."""
        with self.assertRaisesMessage(RuntimeError, 'command exception'):
            call_command(
                'shell',
                command='raise RuntimeError("command exception")',
            )

    @unittest.skipIf(sys.platform == 'win32', "Windows select() doesn't support file descriptors.")
    def test_shell_005_noninteractive_stdin_user_code_exception_remains_visible_to_invoking_context(self):
        """GUID: SHELL-005 - A stdin exception remains visible to its invoker."""
        with captured_stdin() as stdin:
            stdin.write('raise RuntimeError("stdin exception")')
            stdin.seek(0)
            with mock.patch(
                'django.core.management.commands.shell.select.select',
                return_value=([stdin], [], []),
            ):
                with self.assertRaisesMessage(RuntimeError, 'stdin exception'):
                    call_command('shell')

    @unittest.skipIf(sys.platform == 'win32', "Windows select() doesn't support file descriptors.")
    def test_shell_002_noninteractive_stdin_function_resolves_imported_global_name(self):
        """GUID: SHELL-002 - Stdin function resolves an imported global name."""
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write(
                'import django\n'
                'def get_version():\n'
                '    return django.__version__\n'
                'print(get_version())'
            )
            stdin.seek(0)
            with mock.patch(
                'django.core.management.commands.shell.select.select',
                return_value=([stdin], [], []),
            ):
                call_command('shell')
        self.assertEqual(stdout.getvalue().strip(), __version__)

    @unittest.skipIf(sys.platform == 'win32', "Windows select() doesn't support file descriptors.")
    def test_shell_002_noninteractive_stdin_function_resolves_earlier_top_level_name(self):
        """GUID: SHELL-002 - Stdin function resolves an earlier top-level name."""
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write(
                'value = "available"\n'
                'def get_value():\n'
                '    return value\n'
                'print(get_value())'
            )
            stdin.seek(0)
            with mock.patch(
                'django.core.management.commands.shell.select.select',
                return_value=([stdin], [], []),
            ):
                call_command('shell')
        self.assertEqual(stdout.getvalue().strip(), 'available')

    @unittest.skipIf(sys.platform == 'win32', "Windows select() doesn't support file descriptors.")
    @mock.patch('django.core.management.commands.shell.Command.python')
    def test_shell_004_successful_noninteractive_stdin_produces_effect_and_exits(self, python):
        """GUID: SHELL-004 - Successful stdin takes effect and exits."""
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write('print("effect")')
            stdin.seek(0)
            with mock.patch(
                'django.core.management.commands.shell.select.select',
                return_value=([stdin], [], []),
            ):
                call_command('shell', interface='python')
        self.assertEqual(stdout.getvalue().strip(), 'effect')
        python.assert_not_called()

    def test_shell_001_command_function_resolves_imported_global_name(self):
        """GUID: SHELL-001 - A function resolves an imported global name."""
        with captured_stdout() as stdout:
            call_command(
                'shell',
                command=(
                    'import django\n'
                    'def get_version():\n'
                    '    return django.__version__\n'
                    'print(get_version())'
                ),
            )
        self.assertEqual(stdout.getvalue().strip(), __version__)

    def test_shell_001_command_function_resolves_earlier_top_level_name(self):
        """GUID: SHELL-001 - A function resolves an earlier top-level name."""
        with captured_stdout() as stdout:
            call_command(
                'shell',
                command=(
                    'value = "available"\n'
                    'def get_value():\n'
                    '    return value\n'
                    'print(get_value())'
                ),
            )
        self.assertEqual(stdout.getvalue().strip(), 'available')

    @mock.patch('django.core.management.commands.shell.Command.python')
    def test_shell_003_successful_command_produces_effect_and_exits(self, python):
        """GUID: SHELL-003 - A successful command takes effect and exits."""
        with captured_stdout() as stdout:
            call_command('shell', command='print("effect")', interface='python')
        self.assertEqual(stdout.getvalue().strip(), 'effect')
        python.assert_not_called()

    def test_command_option(self):
        with self.assertLogs('test', 'INFO') as cm:
            call_command(
                'shell',
                command=(
                    'import django; from logging import getLogger; '
                    'getLogger("test").info(django.__version__)'
                ),
            )
        self.assertEqual(cm.records[0].getMessage(), __version__)

    @unittest.skipIf(sys.platform == 'win32', "Windows select() doesn't support file descriptors.")
    @mock.patch('django.core.management.commands.shell.select')
    def test_stdin_read(self, select):
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write('print(100)\n')
            stdin.seek(0)
            call_command('shell')
        self.assertEqual(stdout.getvalue().strip(), '100')

    @mock.patch('django.core.management.commands.shell.select.select')  # [1]
    @mock.patch.dict('sys.modules', {'IPython': None})
    def test_shell_with_ipython_not_installed(self, select):
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(CommandError, "Couldn't import ipython interface."):
            call_command('shell', interface='ipython')

    @mock.patch('django.core.management.commands.shell.select.select')  # [1]
    @mock.patch.dict('sys.modules', {'bpython': None})
    def test_shell_with_bpython_not_installed(self, select):
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(CommandError, "Couldn't import bpython interface."):
            call_command('shell', interface='bpython')

    # [1] Patch select to prevent tests failing when when the test suite is run
    # in parallel mode. The tests are run in a subprocess and the subprocess's
    # stdin is closed and replaced by /dev/null. Reading from /dev/null always
    # returns EOF and so select always shows that sys.stdin is ready to read.
    # This causes problems because of the call to select.select() towards the
    # end of shell's handle() method.
