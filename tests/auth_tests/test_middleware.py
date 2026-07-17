import base64
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY,
)
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.models import Session
from django.http import HttpRequest, HttpResponse
from django.test import TestCase, override_settings
from django.test.utils import ignore_warnings
from django.utils import timezone
from django.utils.deprecation import RemovedInDjango40Warning


class MalformedPersistedSessionAuthenticationContractTests(TestCase):
    """SES-008 malformed persisted session authentication contract."""

    session_key = 'malformed-authentication-session'
    malformed_values = {
        SESSION_KEY: 'malformed-user-id',
        BACKEND_SESSION_KEY: 'malformed-backend',
        HASH_SESSION_KEY: 'malformed-session-hash',
    }

    @classmethod
    def setUpTestData(cls):
        session_store = SessionStore()
        encoded = session_store._legacy_encode(cls.malformed_values)
        serialized = base64.b64decode(encoded).split(b':', 1)[1]
        Session.objects.create(
            session_key=cls.session_key,
            session_data=base64.b64encode(
                b'invalid-signature:' + serialized
            ).decode('ascii'),
            expire_date=timezone.now() + timedelta(days=1),
        )

    def process_request(self):
        def get_response(request):
            self.user_is_anonymous = request.user.is_anonymous
            self.exposed_session = dict(request.session)
            return HttpResponse()

        middleware = SessionMiddleware(AuthenticationMiddleware(get_response))
        request = HttpRequest()
        request.COOKIES[settings.SESSION_COOKIE_NAME] = self.session_key
        with self.assertLogs(
            'django.security.SuspiciousSession', 'WARNING'
        ):
            return middleware(request)

    def test_SES_008_authentication_access_to_malformed_persisted_session_completes_without_decoding_exception(self):
        """SES-008: authentication and session processing contain decode failure."""
        self.process_request()

        self.assertTrue(self.user_is_anonymous)

    def test_SES_008_authentication_access_to_malformed_persisted_session_produces_no_internal_server_error(self):
        """SES-008: malformed persisted data produces no internal server error."""
        response = self.process_request()

        self.assertEqual(response.status_code, 200)

    def test_SES_008_authentication_access_to_malformed_persisted_session_exposes_no_malformed_values(self):
        """SES-008: authentication processing receives no malformed values."""
        self.process_request()

        self.assertEqual(self.exposed_session, {})
        for value in self.malformed_values.values():
            self.assertNotIn(value, self.exposed_session.values())


class TestAuthenticationMiddleware(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('test_user', 'test@example.com', 'test_password')

    def setUp(self):
        self.middleware = AuthenticationMiddleware(lambda req: HttpResponse())
        self.client.force_login(self.user)
        self.request = HttpRequest()
        self.request.session = self.client.session

    def test_no_password_change_doesnt_invalidate_session(self):
        self.request.session = self.client.session
        self.middleware(self.request)
        self.assertIsNotNone(self.request.user)
        self.assertFalse(self.request.user.is_anonymous)

    def test_no_password_change_does_not_invalidate_legacy_session(self):
        # RemovedInDjango40Warning: pre-Django 3.1 hashes will be invalid.
        session = self.client.session
        session[HASH_SESSION_KEY] = self.user._legacy_get_session_auth_hash()
        session.save()
        self.request.session = session
        self.middleware(self.request)
        self.assertIsNotNone(self.request.user)
        self.assertFalse(self.request.user.is_anonymous)

    @ignore_warnings(category=RemovedInDjango40Warning)
    def test_session_default_hashing_algorithm(self):
        hash_session = self.client.session[HASH_SESSION_KEY]
        with override_settings(DEFAULT_HASHING_ALGORITHM='sha1'):
            self.assertNotEqual(hash_session, self.user.get_session_auth_hash())

    def test_changed_password_invalidates_session(self):
        # After password change, user should be anonymous
        self.user.set_password('new_password')
        self.user.save()
        self.middleware(self.request)
        self.assertIsNotNone(self.request.user)
        self.assertTrue(self.request.user.is_anonymous)
        # session should be flushed
        self.assertIsNone(self.request.session.session_key)

    def test_no_session(self):
        msg = (
            "The Django authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'django.contrib.auth.middleware.AuthenticationMiddleware'."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.middleware(HttpRequest())
