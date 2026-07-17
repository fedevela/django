import signal

from django.db.backends.base.client import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
    executable_name = "psql"

    # Architecture contract for GUIDs PGSQL-005, PGSQL-006, and PGSQL-007:
    # This backend-owned translation seam is solely responsible for preserving
    # PostgreSQL connection-setting semantics while composing the ordered argv
    # and environment consumed by BaseDatabaseClient.runshell(). User-supplied
    # parameters form an indivisible ordered segment, followed only by a
    # configured database name; absence of that name crosses this boundary as
    # absence, not as an empty or synthesized positional argument. The inherited
    # runner remains the process-launch boundary; dependency stays directed from
    # this backend translator into that inherited runner, with no new adapter or
    # public API.
    @classmethod
    def settings_to_cmd_args_env(cls, settings_dict, parameters):
        args = [cls.executable_name]
        options = settings_dict.get("OPTIONS", {})

        host = settings_dict.get("HOST")
        port = settings_dict.get("PORT")
        dbname = settings_dict.get("NAME")
        user = settings_dict.get("USER")
        passwd = settings_dict.get("PASSWORD")
        passfile = options.get("passfile")
        service = options.get("service")
        sslmode = options.get("sslmode")
        sslrootcert = options.get("sslrootcert")
        sslcert = options.get("sslcert")
        sslkey = options.get("sslkey")

        # Pseudocode for GUIDs PGSQL-005, PGSQL-006, PGSQL-007:
        # - INPUT: established connection settings and the ordered ``parameters``.
        # - INITIALIZE the command with ``psql``.
        # - FOR EACH established command setting (user, host, port), when present:
        #     - append its established option and value without changing meaning;
        #       retain password, service, passfile, and SSL settings for their
        #       established environment-variable mapping. [PGSQL-005]
        # - APPEND every parameter once, unchanged and in input order. [PGSQL-007]
        # - IF a configured database name is present:
        #     - append that name after all parameters. [PGSQL-005/006]
        #     - IF parameters is empty, hand off ``psql`` followed by that name so
        #       the normal interactive shell opens. [PGSQL-006]
        # - ELSE, when no database name is configured:
        #     - append no database-name argument: neither an empty value nor a
        #       synthesized name; hand off all parameters unchanged. [PGSQL-007]
        # - OUTPUT: the ordered command plus the established environment mapping;
        #   propagate construction or process-launch failures unchanged.
        if not dbname and not service:
            # Connect to the default 'postgres' db.
            dbname = "postgres"
        if user:
            args += ["-U", user]
        if host:
            args += ["-h", host]
        if port:
            args += ["-p", str(port)]
        args.extend(parameters)
        if dbname:
            args += [dbname]

        env = {}
        if passwd:
            env["PGPASSWORD"] = str(passwd)
        if service:
            env["PGSERVICE"] = str(service)
        if sslmode:
            env["PGSSLMODE"] = str(sslmode)
        if sslrootcert:
            env["PGSSLROOTCERT"] = str(sslrootcert)
        if sslcert:
            env["PGSSLCERT"] = str(sslcert)
        if sslkey:
            env["PGSSLKEY"] = str(sslkey)
        if passfile:
            env["PGPASSFILE"] = str(passfile)
        return args, (env or None)

    def runshell(self, parameters):
        sigint_handler = signal.getsignal(signal.SIGINT)
        try:
            # Allow SIGINT to pass to psql to abort queries.
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            super().runshell(parameters)
        finally:
            # Restore the original SIGINT handler.
            signal.signal(signal.SIGINT, sigint_handler)
