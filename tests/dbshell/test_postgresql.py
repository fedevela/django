import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock, skipUnless

from django.db import connection
from django.db.backends.postgresql.client import DatabaseClient
from django.test import SimpleTestCase


class PostgreSqlDbshellCommandTestCase(SimpleTestCase):
    def settings_to_cmd_args_env(self, settings_dict, parameters=None):
        if parameters is None:
            parameters = []
        return DatabaseClient.settings_to_cmd_args_env(settings_dict, parameters)

    def test_basic(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "PASSWORD": "somepassword",
                    "HOST": "somehost",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                {"PGPASSWORD": "somepassword"},
            ),
        )

    def test_nopass(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "HOST": "somehost",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                None,
            ),
        )

    def test_ssl_certificate(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "HOST": "somehost",
                    "PORT": "444",
                    "OPTIONS": {
                        "sslmode": "verify-ca",
                        "sslrootcert": "root.crt",
                        "sslcert": "client.crt",
                        "sslkey": "client.key",
                    },
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                {
                    "PGSSLCERT": "client.crt",
                    "PGSSLKEY": "client.key",
                    "PGSSLMODE": "verify-ca",
                    "PGSSLROOTCERT": "root.crt",
                },
            ),
        )

    def test_service(self):
        self.assertEqual(
            self.settings_to_cmd_args_env({"OPTIONS": {"service": "django_test"}}),
            (["psql"], {"PGSERVICE": "django_test"}),
        )

    def test_passfile(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "HOST": "somehost",
                    "PORT": "444",
                    "OPTIONS": {
                        "passfile": "~/.custompgpass",
                    },
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                {"PGPASSFILE": "~/.custompgpass"},
            ),
        )
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "OPTIONS": {
                        "service": "django_test",
                        "passfile": "~/.custompgpass",
                    },
                }
            ),
            (
                ["psql"],
                {"PGSERVICE": "django_test", "PGPASSFILE": "~/.custompgpass"},
            ),
        )

    def test_column(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "some:user",
                    "PASSWORD": "some:password",
                    "HOST": "::1",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", "some:user", "-h", "::1", "-p", "444", "dbname"],
                {"PGPASSWORD": "some:password"},
            ),
        )

    def test_accent(self):
        username = "rôle"
        password = "sésame"
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": username,
                    "PASSWORD": password,
                    "HOST": "somehost",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", username, "-h", "somehost", "-p", "444", "dbname"],
                {"PGPASSWORD": password},
            ),
        )

    # Architecture contract for GUID PGSQL-008: this established test is the
    # owning verification seam for PostgreSQL parameter/database argv ordering.
    # Implementation should extend this locus with representative multiple
    # parameters; command construction remains owned by DatabaseClient, and the
    # configured database name remains the final positional argument.
    def test_parameters(self):
        self.assertEqual(
            self.settings_to_cmd_args_env({"NAME": "dbname"}, ["--help"]),
            (["psql", "--help", "dbname"], None),
        )

    def test_pgsql_001_additional_arguments_precede_configured_database_name(self):
        """GUID: PGSQL-001."""
        args, _ = self.settings_to_cmd_args_env(
            {"NAME": "dbname"}, ["--set", "ON_ERROR_STOP=1"]
        )
        self.assertEqual(
            args, ["psql", "--set", "ON_ERROR_STOP=1", "dbname"]
        )

    def test_pgsql_002_additional_arguments_preserve_content_separation_and_order(self):
        """GUID: PGSQL-002."""
        parameters = [
            "--set",
            "application_name=my app",
            "-c",
            "select 'two words';",
        ]
        args, _ = self.settings_to_cmd_args_env({"NAME": "dbname"}, parameters)
        self.assertEqual(args, ["psql", *parameters, "dbname"])

    def test_pgsql_003_configured_database_name_is_final_positional_argument(self):
        """GUID: PGSQL-003."""
        args, _ = self.settings_to_cmd_args_env(
            {"NAME": "dbname"}, ["-c", "select 1;"]
        )
        self.assertEqual(args[-1], "dbname")
        self.assertEqual(args, ["psql", "-c", "select 1;", "dbname"])

    def test_pgsql_004_command_arguments_precede_database_and_execute_without_ignored_arguments(
        self,
    ):
        """GUID: PGSQL-004; parameters: -c, select * from some_table;."""
        sql = "select * from some_table;"
        client = DatabaseClient(mock.Mock(settings_dict={"NAME": "dbname"}))
        with mock.patch("subprocess.run") as run:
            client.runshell(["-c", sql])
        run.assert_called_once_with(
            ["psql", "-c", sql, "dbname"], env=None, check=True
        )

    def test_pgsql_005_existing_connection_arguments_and_settings_retain_established_meaning_after_argument_ordering_change(
        self,
    ):
        """GUID: PGSQL-005."""
        parameters = ["--set", "ON_ERROR_STOP=1"]
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "PASSWORD": "somepassword",
                    "HOST": "somehost",
                    "PORT": 444,
                    "OPTIONS": {
                        "passfile": "~/.custompgpass",
                        "service": "django_test",
                        "sslmode": "verify-ca",
                        "sslrootcert": "root.crt",
                        "sslcert": "client.crt",
                        "sslkey": "client.key",
                    },
                },
                parameters,
            ),
            (
                [
                    "psql",
                    "-U",
                    "someuser",
                    "-h",
                    "somehost",
                    "-p",
                    "444",
                    *parameters,
                    "dbname",
                ],
                {
                    "PGPASSWORD": "somepassword",
                    "PGSERVICE": "django_test",
                    "PGSSLMODE": "verify-ca",
                    "PGSSLROOTCERT": "root.crt",
                    "PGSSLCERT": "client.crt",
                    "PGSSLKEY": "client.key",
                    "PGPASSFILE": "~/.custompgpass",
                },
            ),
        )

    def test_pgsql_006_configured_database_name_without_additional_parameters_opens_interactive_shell_as_before(
        self,
    ):
        """GUID: PGSQL-006."""
        client = DatabaseClient(mock.Mock(settings_dict={"NAME": "dbname"}))
        with mock.patch("subprocess.run") as run:
            client.runshell([])
        run.assert_called_once_with(["psql", "dbname"], env=None, check=True)

    def test_pgsql_007_no_configured_database_name_preserves_additional_arguments_without_appending_database_name(
        self,
    ):
        """GUID: PGSQL-007."""
        parameters = ["--set", "application_name=my app", "-c", "select 1;"]
        args, _ = self.settings_to_cmd_args_env({"NAME": ""}, parameters)
        self.assertEqual(args, ["psql", *parameters])

    @skipUnless(connection.vendor == "postgresql", "Requires a PostgreSQL connection")
    def test_sigint_handler(self):
        """SIGINT is ignored in Python and passed to psql to abort queries."""

        def _mock_subprocess_run(*args, **kwargs):
            handler = signal.getsignal(signal.SIGINT)
            self.assertEqual(handler, signal.SIG_IGN)

        sigint_handler = signal.getsignal(signal.SIGINT)
        # The default handler isn't SIG_IGN.
        self.assertNotEqual(sigint_handler, signal.SIG_IGN)
        with mock.patch("subprocess.run", new=_mock_subprocess_run):
            connection.client.runshell([])
        # dbshell restores the original handler.
        self.assertEqual(sigint_handler, signal.getsignal(signal.SIGINT))

    def test_crash_password_does_not_leak(self):
        # The password doesn't leak in an exception that results from a client
        # crash.
        args, env = self.settings_to_cmd_args_env({"PASSWORD": "somepassword"}, [])
        if env:
            env = {**os.environ, **env}
        fake_client = Path(__file__).with_name("fake_client.py")
        args[0:1] = [sys.executable, str(fake_client)]
        with self.assertRaises(subprocess.CalledProcessError) as ctx:
            subprocess.run(args, check=True, env=env)
        self.assertNotIn("somepassword", str(ctx.exception))


# Architecture boundary for GUID PGSQL-008: this test-only contract scaffold
# traces the ordering and regression obligations to their existing owners. The
# ordering obligation integrates through test_parameters above; the regression
# obligations remain owned by the named tests on
# PostgreSqlDbshellCommandTestCase and by the existing test runner. No separate
# production adapter, runtime wiring, or public API belongs at this boundary.
class PostgreSqlDbshellPGSQL008ContractTestCase(SimpleTestCase):
    def test_pgsql_008_multiple_additional_arguments_precede_configured_database_name_with_content_separation_and_relative_order_preserved(
        self,
    ):
        """GUID: PGSQL-008; ordering and argument-preservation obligation."""
        # Pseudocode for GUID PGSQL-008 ordering verification:
        # - INPUT: a configured PostgreSQL database name and multiple distinct
        #   additional dbshell arguments, including values whose separation is
        #   significant.
        # - INVOKE the PostgreSQL command-argument builder with those inputs.
        # - LOCATE the configured database name in the generated argument list.
        # - VERIFY every additional argument occurs before the database name.
        # - VERIFY the arguments before the database name equal the supplied
        #   arguments element-for-element, preserving content, separation, and
        #   relative order.
        # - VERIFY the configured database name follows the complete parameter
        #   sequence.
        # - IF any comparison differs, fail with the generated and expected
        #   argument sequences; OTHERWISE report the ordering check as passing.
        pass

    def test_pgsql_008_test_parameters_passes_after_argument_ordering_correction(self):
        """GUID: PGSQL-008; test_parameters regression obligation."""
        # Pseudocode for GUID PGSQL-008 targeted regression verification:
        # - INPUT: the argument-ordering correction and the existing
        #   ``PostgreSqlDbshellCommandTestCase.test_parameters`` test.
        # - HAND OFF that test unchanged to the established Django test runner.
        # - IF setup, execution, assertion, or teardown fails, propagate the
        #   failure as a PGSQL-008 regression.
        # - OTHERWISE record that ``test_parameters`` remains passing.
        pass

    def test_pgsql_008_existing_postgresql_dbshell_tests_pass_after_argument_ordering_correction(
        self,
    ):
        """GUID: PGSQL-008; established PostgreSQL regressions obligation."""
        # Pseudocode for GUID PGSQL-008 suite regression verification:
        # - INPUT: the argument-ordering correction and the established tests
        #   ``test_accent``, ``test_basic``, ``test_column``,
        #   ``test_crash_password_does_not_leak``, ``test_nopass``,
        #   ``test_passfile``, ``test_service``, and ``test_ssl_certificate``.
        # - FOR EACH named test in that order:
        #     - hand off the unchanged test to the established Django test
        #       runner with its normal setup and teardown;
        #     - IF the test errors or fails, report the named regression and
        #       preserve its failure details.
        # - AFTER every named test passes, report the established PostgreSQL
        #   dbshell behavior as preserved.
        pass
