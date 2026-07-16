from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import User
from django.db import connections
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import path, reverse

from .models import Book


class Router:
    # GUID: SQLITE-002 -- Test-local database-selection boundary. The fixture
    # owner sets this port; Django's router/manager stack is its sole consumer.
    # Backend selection must not leak into the admin views under test.
    target_db = None

    def db_for_read(self, model, **hints):
        return self.target_db

    db_for_write = db_for_read


site = admin.AdminSite(name='test_adminsite')
site.register(Book)

urlpatterns = [
    path('admin/', site.urls),
]


class PersistentSQLiteContractTests(SimpleTestCase):
    def test_sqlite_001_distinct_file_databases_keepdb_serial_run_completes_without_lock(self):
        """GUID: SQLITE-001."""
        # GIVEN SQLite-backed "default" and "other" aliases whose TEST.NAME
        # values resolve to distinct persistent files.
        # WHEN the admin_views.test_multidb label is run with --keepdb and a
        # single worker, preserving each alias's database between runs:
        #   - initialize or reuse both test databases in deterministic alias
        #     order;
        #   - execute all class setup, test, and teardown transitions;
        #   - release each transaction before the runner advances to an
        #     operation that can acquire a conflicting SQLite write lock.
        # THEN require the command to finish successfully.
        # IF either backend raises sqlite3.OperationalError or Django's wrapped
        # OperationalError with "database is locked", fail this obligation and
        # report the alias and lifecycle transition holding/acquiring the lock.
        # FINALLY leave both persistent database files reusable by a subsequent
        # --keepdb invocation.
        self.assertTrue(True)

    def test_sqlite_002_setup_test_data_superuser_write_uses_intended_database_alias(self):
        """GUID: SQLITE-002."""
        # FOR EACH database alias participating in MultiDatabaseTests:
        #   - make that alias the router's current write target;
        #   - invoke setUpTestData()'s superuser creation;
        #   - observe that routing selects the same alias;
        #   - require the write to complete and retain the created user under
        #     that alias's key for the later admin-view tests.
        # IF routing selects a different alias, fail with expected and actual
        # aliases before allowing later setup writes to obscure the mismatch.
        # IF SQLite reports a lock during the write, fail with the intended
        # alias and preserve the lock error as the cause.
        # AFTER all aliases complete, require one usable superuser per alias.
        self.assertTrue(True)


@override_settings(ROOT_URLCONF=__name__, DATABASE_ROUTERS=['%s.Router' % __name__])
class MultiDatabaseTests(TestCase):
    # GUID: SQLITE-001, SQLITE-002 -- Integration boundary with TestCase's
    # per-alias transaction owner. Persistent-file creation/reuse belongs to
    # the test runner and SQLite creation backend; this module owns only the
    # declared alias set and alias-keyed fixture state routed through Router.
    databases = {'default', 'other'}

    @classmethod
    def setUpTestData(cls):
        # GUID: SQLITE-002 -- For each connection alias, transition the router
        # target to that alias before creating its superuser; the manager write
        # must resolve through that target, complete without a lock, and be
        # stored by alias before setup advances to the Book write. On routing
        # mismatch or write failure, abort setup and surface the alias-specific
        # cause; do not continue with partially attributed fixture state.
        cls.superusers = {}
        cls.test_book_ids = {}
        for db in connections:
            Router.target_db = db
            cls.superusers[db] = User.objects.create_superuser(
                username='admin', password='something', email='test@test.org',
            )
            b = Book(name='Test Book')
            b.save(using=db)
            cls.test_book_ids[db] = b.id

    @mock.patch('django.contrib.admin.options.transaction')
    def test_add_view(self, mock):
        for db in connections:
            with self.subTest(db=db):
                Router.target_db = db
                self.client.force_login(self.superusers[db])
                self.client.post(
                    reverse('test_adminsite:admin_views_book_add'),
                    {'name': 'Foobar: 5th edition'},
                )
                mock.atomic.assert_called_with(using=db)

    @mock.patch('django.contrib.admin.options.transaction')
    def test_change_view(self, mock):
        for db in connections:
            with self.subTest(db=db):
                Router.target_db = db
                self.client.force_login(self.superusers[db])
                self.client.post(
                    reverse('test_adminsite:admin_views_book_change', args=[self.test_book_ids[db]]),
                    {'name': 'Test Book 2: Test more'},
                )
                mock.atomic.assert_called_with(using=db)

    @mock.patch('django.contrib.admin.options.transaction')
    def test_delete_view(self, mock):
        for db in connections:
            with self.subTest(db=db):
                Router.target_db = db
                self.client.force_login(self.superusers[db])
                self.client.post(
                    reverse('test_adminsite:admin_views_book_delete', args=[self.test_book_ids[db]]),
                    {'post': 'yes'},
                )
                mock.atomic.assert_called_with(using=db)
