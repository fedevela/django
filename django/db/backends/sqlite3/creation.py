import os
import shutil
import sys
from pathlib import Path

from django.db.backends.base.creation import BaseDatabaseCreation


class DatabaseCreation(BaseDatabaseCreation):

    @staticmethod
    def is_in_memory_db(database_name):
        return not isinstance(database_name, Path) and (
            database_name == ':memory:' or 'mode=memory' in database_name
        )

    def _get_test_db_name(self):
        test_database_name = self.connection.settings_dict['TEST']['NAME'] or ':memory:'
        if test_database_name == ':memory:':
            return 'file:memorydb_%s?mode=memory&cache=shared' % self.connection.alias
        return test_database_name

    # GUID: SQLITE-003 -- Architecture contract for named keepdb creation.
    # This backend override owns SQLite file-name and replacement policy only.
    # BaseDatabaseCreation.create_test_db() owns the downstream alias binding,
    # schema initialization, and connection establishment. The dependency must
    # continue from this override into that base flow for every alias; creation
    # must not open, initialize, or share another alias's connection here.
    # Post-setup writes remain owned by the alias-bound DatabaseWrapper, making
    # this return boundary the integration seam exercised by the SQLite tests.
    #
    # GUID: SQLITE-005 -- Alias isolation is owned across two existing seams.
    # test_db_signature() supplies the SQLite database identity used by
    # get_unique_databases_and_mirrors(), which must keep distinct named test
    # databases in separate setup groups. This hook then supplies only this
    # connection's physical database name to BaseDatabaseCreation.create_test_db().
    # The base creation flow retains ownership of binding that name to the
    # connection alias and passes the same alias to migration, synchronization,
    # and cache setup. Test reads and writes remain owned by that alias-bound
    # DatabaseWrapper. Dependencies therefore flow from test-runner grouping to
    # this backend's identity/file policy, then back through the base lifecycle;
    # neither backend creation nor later operations may substitute the peer
    # alias's name or connection.
    #
    # GUID: SQLITE-004, SQLITE-006 -- Architecture contract for named database
    # reuse. This override owns the decision to preserve and admit the existing
    # SQLite file, but must not own connection or transaction state. After this
    # hook returns, BaseDatabaseCreation.create_test_db() owns the close/rebind
    # boundary and the normal migration and synchronization flow. The resulting
    # alias-bound DatabaseWrapper owns post-setup writes to the preserved file.
    #
    # GUID: SQLITE-007 -- Repeated reuse crosses the same boundary on every run:
    # BaseDatabaseCreation.destroy_test_db() closes the active wrapper before
    # preserving the file, and the next create_test_db() call re-enters here.
    # Dependencies therefore point from the test-runner lifecycle through the
    # base creation contract into this SQLite preservation policy, never from
    # this hook to a retained connection from an earlier run.
    def _create_test_db(self, verbosity, autoclobber, keepdb=False):
        test_database_name = self._get_test_db_name()

        # GUID: SQLITE-003 -- Returning a named database, even when its file is
        # missing, lets the base creation flow bind it to this alias, initialize
        # it, and open the connection that creates the SQLite file. Database
        # errors remain visible to the test runner.
        if keepdb:
            return test_database_name
        if not self.is_in_memory_db(test_database_name):
            # Erase the old test database
            if verbosity >= 1:
                self.log('Destroying old test database for alias %s...' % (
                    self._get_database_display_str(verbosity, test_database_name),
                ))
            if os.access(test_database_name, os.F_OK):
                if not autoclobber:
                    confirm = input(
                        "Type 'yes' if you would like to try deleting the test "
                        "database '%s', or 'no' to cancel: " % test_database_name
                    )
                if autoclobber or confirm == 'yes':
                    try:
                        os.remove(test_database_name)
                    except Exception as e:
                        self.log('Got an error deleting the old test database: %s' % e)
                        sys.exit(2)
                else:
                    self.log('Tests cancelled.')
                    sys.exit(1)
        return test_database_name

    def get_test_db_clone_settings(self, suffix):
        orig_settings_dict = self.connection.settings_dict
        source_database_name = orig_settings_dict['NAME']
        if self.is_in_memory_db(source_database_name):
            return orig_settings_dict
        else:
            root, ext = os.path.splitext(orig_settings_dict['NAME'])
            return {**orig_settings_dict, 'NAME': '{}_{}.{}'.format(root, suffix, ext)}

    def _clone_test_db(self, suffix, verbosity, keepdb=False):
        source_database_name = self.connection.settings_dict['NAME']
        target_database_name = self.get_test_db_clone_settings(suffix)['NAME']
        # Forking automatically makes a copy of an in-memory database.
        if not self.is_in_memory_db(source_database_name):
            # Erase the old test database
            if os.access(target_database_name, os.F_OK):
                if keepdb:
                    return
                if verbosity >= 1:
                    self.log('Destroying old test database for alias %s...' % (
                        self._get_database_display_str(verbosity, target_database_name),
                    ))
                try:
                    os.remove(target_database_name)
                except Exception as e:
                    self.log('Got an error deleting the old test database: %s' % e)
                    sys.exit(2)
            try:
                shutil.copy(source_database_name, target_database_name)
            except Exception as e:
                self.log('Got an error cloning the test database: %s' % e)
                sys.exit(2)

    def _destroy_test_db(self, test_database_name, verbosity):
        if test_database_name and not self.is_in_memory_db(test_database_name):
            # Remove the SQLite database file
            os.remove(test_database_name)

    def test_db_signature(self):
        """
        Return a tuple that uniquely identifies a test database.

        This takes into account the special cases of ":memory:" and "" for
        SQLite since the databases will be distinct despite having the same
        TEST NAME. See https://www.sqlite.org/inmemorydb.html
        """
        test_database_name = self._get_test_db_name()
        sig = [self.connection.settings_dict['NAME']]
        if self.is_in_memory_db(test_database_name):
            sig.append(self.connection.alias)
        else:
            # GUID: SQLITE-001, SQLITE-002 -- Named test databases must remain
            # distinct so multiple aliases aren't configured as mirrors.
            sig.append(test_database_name)
        return tuple(sig)
