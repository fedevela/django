from django.apps.registry import Apps
from django.db import DatabaseError, models, router
from django.utils.functional import classproperty
from django.utils.timezone import now

from .exceptions import MigrationSchemaMissing


# MIGREC-003, MIGREC-004, MIGREC-005, MIGREC-006, MIGREC-007 architecture boundary:
# MigrationRecorder owns both recorder-storage permission and the existing
# schema/read/write contract for a single connection. Keep the router dependency
# behind one private recorder-level permission seam, using this recorder's
# connection alias and Migration model; permitted operations continue through
# the existing has_table(), ensure_schema(), and migration_qs collaborators.
#
# MigrationLoader and MigrationExecutor depend only on the recorder's public
# storage contract and remain unaware of routing. Their existing per-connection
# recorder composition is the multi-database isolation seam: never share routing
# state or recorder storage across aliases, and don't move recorder permission
# decisions into those callers.
class MigrationRecorder:
    """
    Deal with storing migration records in the database.

    Because this table is actually itself used for dealing with model
    creation, it's the one thing we can't do normally via migrations.
    We manually handle table creation/schema updating (using schema backend)
    and then have a floating model to do queries with.

    If a migration is unapplied its row is removed from the table. Having
    a row in the table always means a migration is applied.
    """
    _migration_class = None

    @classproperty
    def Migration(cls):
        """
        Lazy load to avoid AppRegistryNotReady if installed apps import
        MigrationRecorder.
        """
        if cls._migration_class is None:
            class Migration(models.Model):
                app = models.CharField(max_length=255)
                name = models.CharField(max_length=255)
                applied = models.DateTimeField(default=now)

                class Meta:
                    apps = Apps()
                    app_label = 'migrations'
                    db_table = 'django_migrations'

                def __str__(self):
                    return 'Migration %s for %s' % (self.name, self.app)

            cls._migration_class = Migration
        return cls._migration_class

    def __init__(self, connection):
        self.connection = connection

    @property
    def migration_qs(self):
        return self.Migration.objects.using(self.connection.alias)

    def has_table(self):
        """Return True if the django_migrations table exists."""
        with self.connection.cursor() as cursor:
            tables = self.connection.introspection.table_names(cursor)
        return self.Migration._meta.db_table in tables

    def _migration_allowed(self):
        # MIGREC-007 logic obligation: keep migration-history state isolated
        # to each recorder connection while allowing processing to continue.
        # INPUT: the alias bound to this recorder and the recorder model.
        # DECIDE: ask the routers whether that model may migrate on this alias.
        # HANDOFF: each recorder operation uses this result independently;
        # permitted aliases follow their normal history path, while denied
        # aliases return without requiring recorder storage. A decision for
        # one alias never changes the state or decision for another alias.
        return router.allow_migrate_model(self.connection.alias, self.Migration)

    def ensure_schema(self):
        """Ensure the table exists and has the correct schema."""
        # MIGREC-006 logic obligation: preserve permitted schema creation.
        # INPUT: a recorder bound to its connection.
        # IF permission is denied: finish without schema inspection or change.
        # ELSE IF the recorder table exists: finish with the schema unchanged.
        # ELSE: create the recorder model through the connection schema editor.
        # FAILURE: translate a database creation error to
        # MigrationSchemaMissing; otherwise return with the table available.
        if not self._migration_allowed():
            return
        # If the table's there, that's fine - we've never changed its schema
        # in the codebase.
        if self.has_table():
            return
        # Make the table
        try:
            with self.connection.schema_editor() as editor:
                editor.create_model(self.Migration)
        except DatabaseError as exc:
            raise MigrationSchemaMissing("Unable to create the django_migrations table (%s)" % exc)

    def applied_migrations(self):
        """
        Return a dict mapping (app_name, migration_name) to Migration instances
        for all applied migrations.
        """
        # MIGREC-006 logic obligation: preserve permitted history reads.
        # INPUT: a recorder bound to its connection.
        # IF permission is denied: return an empty history without storage I/O.
        # ELSE IF the recorder table is absent: return an empty history.
        # ELSE: read this alias's rows and map each (app, name) to its row.
        # FAILURE: propagate permitted introspection or query errors unchanged.
        # MIGREC-005: Denied reads don't inspect or query django_migrations.
        if not self._migration_allowed():
            return {}
        if self.has_table():
            return {(migration.app, migration.name): migration for migration in self.migration_qs}
        else:
            # If the django_migrations table doesn't exist, then no migrations
            # are applied.
            return {}

    def record_applied(self, app, name):
        """Record that a migration was applied."""
        # MIGREC-006 logic obligation: preserve permitted history inserts.
        # INPUT: this alias's recorder plus an application and migration name.
        # IF permission is denied: finish without schema or history storage.
        # ELSE: ensure the recorder schema, then insert the row on this alias.
        # OUTPUT: finish after the existing create operation succeeds.
        # FAILURE: preserve ensure_schema translation and query error behavior.
        # MIGREC-003: Denied writes don't inspect or create django_migrations.
        if not self._migration_allowed():
            return
        self.ensure_schema()
        self.migration_qs.create(app=app, name=name)

    def record_unapplied(self, app, name):
        """Record that a migration was unapplied."""
        # MIGREC-006 logic obligation: preserve permitted history deletions.
        # INPUT: this alias's recorder plus an application and migration name.
        # IF permission is denied: finish without schema or history storage.
        # ELSE: ensure the recorder schema, select the matching row on this
        # alias, and delete it using the existing queryset semantics.
        # OUTPUT: finish after deletion, including when no row matched.
        # FAILURE: preserve ensure_schema translation and query error behavior.
        # MIGREC-004: Denied deletes don't inspect or create django_migrations.
        if not self._migration_allowed():
            return
        self.ensure_schema()
        self.migration_qs.filter(app=app, name=name).delete()

    def flush(self):
        """Delete all migration records. Useful for testing migrations."""
        self.migration_qs.all().delete()
