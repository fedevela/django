from datetime import datetime

from django.conf import settings
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import base36_to_int, int_to_base36


class PasswordResetTokenGenerator:
    """
    Strategy object used to generate and check tokens for the password
    reset mechanism.
    """
    key_salt = "django.contrib.auth.tokens.PasswordResetTokenGenerator"
    algorithm = None
    secret = None

    def __init__(self):
        self.secret = self.secret or settings.SECRET_KEY
        # RemovedInDjango40Warning: when the deprecation ends, replace with:
        # self.algorithm = self.algorithm or 'sha256'
        self.algorithm = self.algorithm or settings.DEFAULT_HASHING_ALGORITHM

    def make_token(self, user):
        """
        Return a token that can be used once to do a password reset
        for the given user.
        """
        return self._make_token_with_timestamp(user, self._num_seconds(self._now()))

    # Architecture contract (GUID: PRT-004, PRT-005):
    # check_token() owns the token-validity lifecycle boundary. Generation and
    # signature validation share _make_token_with_timestamp(), whose private
    # _make_hash_value() dependency remains the single owner of all
    # token-relevant user state. Expiration remains a separate policy boundary
    # owned here through settings.PASSWORD_RESET_TIMEOUT. Email binding must
    # extend the hash-state seam without replacing established state inputs or
    # bypassing this timeout boundary.
    def check_token(self, user, token):
        """
        Check that a password reset token is correct for a given user.
        """
        # Pseudocode contract (GUID: PRT-004, PRT-005, PRT-006):
        # INPUT user, presented_token, current_time, permitted_lifetime
        # IF user or presented_token is absent:
        #     REJECT presented_token
        # PARSE issued_at and signature from presented_token
        # IF parsing fails:
        #     REJECT presented_token
        # DERIVE expected_token from issued_at and the user's current
        # token-relevant state (primary key, password, last login, and
        # effective email), using each supported hashing mode in turn
        # IF presented_token matches no expected_token:
        #     REJECT presented_token  # PRT-005: established state changes
        #                              # PRT-006: validation user differs
        # COMPUTE token_age from current_time and issued_at
        # IF token_age exceeds permitted_lifetime:
        #     REJECT presented_token  # PRT-005: expiration remains effective
        # ACCEPT presented_token      # PRT-004: state unchanged and in lifetime
        if not (user and token):
            return False
        # Parse the token
        try:
            ts_b36, _ = token.split("-")
        except ValueError:
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        if not constant_time_compare(self._make_token_with_timestamp(user, ts), token):
            # RemovedInDjango40Warning: when the deprecation ends, replace
            # with:
            #   return False
            if not constant_time_compare(
                self._make_token_with_timestamp(user, ts, legacy=True),
                token,
            ):
                return False

        # Check the timestamp is within limit.
        if (self._num_seconds(self._now()) - ts) > settings.PASSWORD_RESET_TIMEOUT:
            return False

        return True

    def _make_token_with_timestamp(self, user, timestamp, legacy=False):
        # timestamp is number of seconds since 2001-1-1. Converted to base 36,
        # this gives us a 6 digit string until about 2069.
        ts_b36 = int_to_base36(timestamp)
        hash_string = salted_hmac(
            self.key_salt,
            self._make_hash_value(user, timestamp),
            secret=self.secret,
            # RemovedInDjango40Warning: when the deprecation ends, remove the
            # legacy argument and replace with:
            #   algorithm=self.algorithm,
            algorithm='sha1' if legacy else self.algorithm,
        ).hexdigest()[::2]  # Limit to shorten the URL.
        return "%s-%s" % (ts_b36, hash_string)

    # Architecture contract (GUID: PRT-001, PRT-002, PRT-003):
    # _make_hash_value() owns the configured-email token binding. Keeping the
    # binding at this private hash-input boundary makes generation and
    # validation consume the same state without adding a second integration
    # path. This module depends only on the user contract
    # get_email_field_name() plus tolerant attribute access; it must not depend
    # on a concrete user model or require that the configured attribute exists.
    def _make_hash_value(self, user, timestamp):
        """
        Hash the user's primary key and some user state that's sure to change
        after a password reset to produce a token that invalidated when it's
        used:
        1. The password field will change upon a password reset (even if the
           same password is chosen, due to password salting).
        2. The last_login field will usually be updated very shortly after
           a password reset.
        3. The email address will change if a user requests a password reset
           for another address.
        Failing those things, settings.PASSWORD_RESET_TIMEOUT eventually
        invalidates the token.

        Running this data through salted_hmac() prevents password cracking
        attempts using the reset token, provided the secret isn't compromised.
        """
        # Pseudocode contract (GUID: PRT-006):
        # INPUT token_user, issued_at
        # READ immutable identity discriminator from token_user.primary_key
        # READ remaining token-relevant state, including effective_email
        # COMPOSE signed_state with identity discriminator as a required input
        # OUTPUT signed_state to the shared generation/validation signer
        # ON validation for a different user:
        #     COMPOSE candidate_state with that user's identity discriminator
        #     EVEN IF effective_email equals the token user's effective_email:
        #         candidate_state remains distinct by identity discriminator
        #     HAND OFF signature mismatch to check_token() for rejection
        # Truncate microseconds so that tokens are consistent even if the
        # database doesn't support microseconds.
        login_timestamp = '' if user.last_login is None else user.last_login.replace(microsecond=0, tzinfo=None)
        email_field = user.get_email_field_name()
        email = getattr(user, email_field, '') or ''
        return '%s%s%s%s%s' % (user.pk, user.password, login_timestamp, timestamp, email)

    def _num_seconds(self, dt):
        return int((dt - datetime(2001, 1, 1)).total_seconds())

    def _now(self):
        # Used for mocking in tests
        return datetime.now()


default_token_generator = PasswordResetTokenGenerator()
