"""
Global Django exception and warning classes.
"""


class FieldDoesNotExist(Exception):
    """The requested model field does not exist"""
    pass


class AppRegistryNotReady(Exception):
    """The django.apps registry is not populated yet"""
    pass


class ObjectDoesNotExist(Exception):
    """The requested object does not exist"""
    silent_variable_failure = True


class MultipleObjectsReturned(Exception):
    """The query returned multiple objects when only one was expected."""
    pass


class SuspiciousOperation(Exception):
    """The user did something suspicious"""


class SuspiciousMultipartForm(SuspiciousOperation):
    """Suspect MIME request in multipart form data"""
    pass


class SuspiciousFileOperation(SuspiciousOperation):
    """A Suspicious filesystem operation was attempted"""
    pass


class DisallowedHost(SuspiciousOperation):
    """HTTP_HOST header contains invalid value"""
    pass


class DisallowedRedirect(SuspiciousOperation):
    """Redirect to scheme not in allowed list"""
    pass


class TooManyFieldsSent(SuspiciousOperation):
    """
    The number of fields in a GET or POST request exceeded
    settings.DATA_UPLOAD_MAX_NUMBER_FIELDS.
    """
    pass


class RequestDataTooBig(SuspiciousOperation):
    """
    The size of the request (excluding any file uploads) exceeded
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE.
    """
    pass


class RequestAborted(Exception):
    """The request was closed before it was completed, or timed out."""
    pass


class PermissionDenied(Exception):
    """The user did not have permission to do that"""
    pass


class ViewDoesNotExist(Exception):
    """The requested view does not exist"""
    pass


class MiddlewareNotUsed(Exception):
    """This middleware is not used in this server configuration"""
    pass


class ImproperlyConfigured(Exception):
    """Django is somehow improperly configured"""
    pass


class FieldError(Exception):
    """Some kind of problem with a model field."""
    pass


NON_FIELD_ERRORS = '__all__'


class ValidationError(Exception):
    """An error while validating data."""
    def __init__(self, message, code=None, params=None):
        """
        The `message` argument can be a single error, a list of errors, or a
        dictionary that maps field names to lists of errors. What we define as
        an "error" can be either a simple string or an instance of
        ValidationError with its message attribute set, and what we define as
        list or dictionary can be an actual `list` or `dict` or an instance
        of ValidationError with its `error_list` or `error_dict` attribute set.
        """
        super().__init__(message, code, params)

        if isinstance(message, ValidationError):
            if hasattr(message, 'error_dict'):
                message = message.error_dict
            elif not hasattr(message, 'message'):
                message = message.error_list
            else:
                message, code, params = message.message, message.code, message.params

        if isinstance(message, dict):
            self.error_dict = {}
            for field, messages in message.items():
                if not isinstance(messages, ValidationError):
                    messages = ValidationError(messages)
                self.error_dict[field] = messages.error_list

        elif isinstance(message, list):
            self.error_list = []
            for message in message:
                # Normalize plain strings to instances of ValidationError.
                if not isinstance(message, ValidationError):
                    message = ValidationError(message)
                if hasattr(message, 'error_dict'):
                    self.error_list.extend(sum(message.error_dict.values(), []))
                else:
                    self.error_list.extend(message.error_list)

        else:
            self.message = message
            self.code = code
            self.params = params
            self.error_list = [self]

    @staticmethod
    def _error_list_equal(left, right):
        if len(left) != len(right):
            return False
        unmatched = list(right)
        for error in left:
            for index, candidate in enumerate(unmatched):
                if error == candidate:
                    del unmatched[index]
                    break
            else:
                return False
        return True

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, ValidationError):
            return NotImplemented
        self_has_error_dict = hasattr(self, 'error_dict')
        other_has_error_dict = hasattr(other, 'error_dict')
        if self_has_error_dict or other_has_error_dict:
            if not self_has_error_dict or not other_has_error_dict:
                return False
            if self.error_dict.keys() != other.error_dict.keys():
                return False
            return all(
                self._error_list_equal(errors, other.error_dict[field])
                for field, errors in self.error_dict.items()
            )
        self_has_message = hasattr(self, 'message')
        other_has_message = hasattr(other, 'message')
        if self_has_message != other_has_message:
            return False
        if not self_has_message:
            return self._error_list_equal(self.error_list, other.error_list)
        return (
            self.message == other.message and
            self.code == other.code and
            self.params == other.params
        )

    @staticmethod
    def _hashable_value(value):
        if isinstance(value, dict):
            return (
                'dict',
                frozenset(
                    (key, ValidationError._hashable_value(nested_value))
                    for key, nested_value in value.items()
                ),
            )
        if isinstance(value, list):
            return (
                'list',
                tuple(ValidationError._hashable_value(item) for item in value),
            )
        if isinstance(value, tuple):
            return (
                'tuple',
                tuple(ValidationError._hashable_value(item) for item in value),
            )
        if isinstance(value, (set, frozenset)):
            return (
                'set',
                frozenset(
                    ValidationError._hashable_value(item) for item in value
                ),
            )
        try:
            hash(value)
        except TypeError:
            # Equal instances of an otherwise unsupported unhashable type
            # must still receive the same hash. Collisions are permitted.
            return ('unhashable',)
        return value

    @staticmethod
    def _error_list_hash(errors):
        return hash(tuple(sorted(hash(error) for error in errors)))

    def __hash__(self):
        if hasattr(self, 'error_dict'):
            return hash(frozenset(
                (field, self._error_list_hash(errors))
                for field, errors in self.error_dict.items()
            ))
        if not hasattr(self, 'message'):
            return self._error_list_hash(self.error_list)
        return hash((
            self._hashable_value(self.message),
            self._hashable_value(self.code),
            self._hashable_value(self.params),
        ))

    @property
    def message_dict(self):
        # Trigger an AttributeError if this ValidationError
        # doesn't have an error_dict.
        getattr(self, 'error_dict')

        return dict(self)

    @property
    def messages(self):
        if hasattr(self, 'error_dict'):
            return sum(dict(self).values(), [])
        return list(self)

    def update_error_dict(self, error_dict):
        if hasattr(self, 'error_dict'):
            for field, error_list in self.error_dict.items():
                error_dict.setdefault(field, []).extend(error_list)
        else:
            error_dict.setdefault(NON_FIELD_ERRORS, []).extend(self.error_list)
        return error_dict

    def __iter__(self):
        if hasattr(self, 'error_dict'):
            for field, errors in self.error_dict.items():
                yield field, list(ValidationError(errors))
        else:
            for error in self.error_list:
                message = error.message
                if error.params:
                    message %= error.params
                yield str(message)

    def __str__(self):
        if hasattr(self, 'error_dict'):
            return repr(dict(self))
        return repr(list(self))

    def __repr__(self):
        return 'ValidationError(%s)' % self


class EmptyResultSet(Exception):
    """A database query predicate is impossible."""
    pass


class SynchronousOnlyOperation(Exception):
    """The user tried to call a sync-only function from an async context."""
    pass
