import signal

from django.db.backends.base.client import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
    executable_name = "psql"

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

        if not dbname and not service:
            # Connect to the default 'postgres' db.
            dbname = "postgres"
        if user:
            args += ["-U", user]
        if host:
            args += ["-h", host]
        if port:
            args += ["-p", str(port)]
        # Pseudocode for GUIDs PGSQL-001, PGSQL-002, PGSQL-003, PGSQL-004:
        # - INPUT: the ordered ``parameters`` sequence and optional ``dbname``.
        # - FOR EACH parameter, in its original order:
        #     - append that parameter as one unchanged argument; do not split, join,
        #       normalize, or otherwise reinterpret its content. [PGSQL-001/002]
        # - IF ``dbname`` is present:
        #     - append it after every parameter, making it the final
        #       database-specific positional argument. [PGSQL-001/003]
        # - ELSE:
        #     - add no database-name positional argument.
        # - HAND OFF the resulting argument list unchanged to ``psql``; therefore,
        #   parameters (``-c``, ``select * from some_table;``) remain two ordered
        #   arguments before ``dbname``, so neither becomes an ignored extra
        #   argument and ``psql`` can execute the command. [PGSQL-002/004]
        if dbname:
            args += [dbname]
        args.extend(parameters)

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
