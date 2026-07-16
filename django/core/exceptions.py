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

    # Equality architecture (VEQ-001, VEQ-002, VEQ-009, VEQ-010, VEQ-011,
    # VEQ-012): ValidationError.__eq__ owns the value-comparison boundary and
    # belongs here, beside the state established by __init__. Its value
    # contract is the stored message, code, and params triplet; the type gate
    # remains inside that method so unrelated operands cannot enter the state
    # comparison boundary. The dependency direction is from equality to this
    # stored state only -- not through message_dict, messages, __iter__, or any
    # normalization/presentation helper. This keeps comparison read-only and
    # prevents equality from acquiring mutation or formatting dependencies.

    # ValidationError equality procedure (VEQ-001, VEQ-002, VEQ-009,
    # VEQ-010, VEQ-011, VEQ-012):
    #
    # def __eq__(self, other):
    #     IF self and other are the same object:                         # VEQ-009
    #         RETURN true
    #     IF other is not a ValidationError:                             # VEQ-011
    #         RETURN false without inspecting ValidationError content
    #     READ each error's message, code, and parameters without
    #         formatting, normalizing, reordering, or assigning them     # VEQ-012
    #     COMPARE the two messages, the two codes, and the two parameter
    #         values using the same component-wise relation              # VEQ-001
    #     IF every corresponding component is equivalent:
    #         RETURN true
    #     RETURN false when any corresponding component differs          # VEQ-002
    #
    # The component relation and branches are independent of operand
    # position, so reversing two ValidationError operands preserves the
    # result.                                                             # VEQ-010
    # Neither the successful nor failure path modifies either error or
    # any validation content reachable from it.                           # VEQ-012

    # Structured equality architecture (VEQ-003, VEQ-004, VEQ-005, VEQ-006,
    # VEQ-007, VEQ-008): __init__ remains the normalization boundary and
    # __eq__ owns comparison of its error_dict/error_list products. Mapping
    # keys define field ownership; each mapped list is a separate occurrence
    # collection, with NON_FIELD_ERRORS flowing through that same contract.
    # Any collection-matching seam is a private implementation detail colocated
    # with ValidationError, and depends inward on normalized leaf equality. It
    # must not depend on dict/list insertion order, presentation properties,
    # formatted messages, hashing, or mutation, and must not become public API.

    # Structured ValidationError equality procedure (VEQ-003, VEQ-004,
    # VEQ-005, VEQ-006, VEQ-007, VEQ-008):
    #
    # equivalent_error_collection(left_errors, right_errors):
    #     IF the collections have different lengths:
    #         RETURN false because duplicate occurrence counts differ     # VEQ-007
    #     MARK every right-side occurrence as unmatched
    #     FOR each normalized leaf error in left_errors:
    #         FIND an unmatched equivalent leaf error in right_errors
    #             using the scalar message, code, and params procedure
    #         IF no such occurrence exists:
    #             RETURN false
    #         MARK that one right-side occurrence as matched
    #     RETURN true; collection order has not affected the result       # VEQ-003
    #
    # compare_structured_content(self, other):
    #     DETERMINE whether each operand owns an error_dict
    #     IF exactly one operand owns an error_dict:
    #         RETURN false because their normalized structures differ
    #     IF both operands own an error_dict:
    #         IF their field-key sets differ:
    #             RETURN false; errors cannot move between fields         # VEQ-006
    #         FOR each field key, independent of dictionary iteration
    #             or insertion order:                                    # VEQ-005
    #             COMPARE the corresponding normalized error lists with
    #                 equivalent_error_collection
    #             IF a corresponding collection differs:
    #                 RETURN false
    #         RETURN true, including when the corresponding field is
    #             NON_FIELD_ERRORS and only error order differs           # VEQ-004
    #     COMPARE the operands' normalized error_lists with
    #         equivalent_error_collection
    #     RETURN that result; constructor-flattened nested content is
    #         therefore compared by corresponding normalized collections,
    #         ignoring only their permitted ordering                      # VEQ-008
    #
    # __eq__ invokes compare_structured_content before the scalar procedure
    # whenever either operand represents list or dictionary content.

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
            return False
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
        if not hasattr(self, 'message') or not hasattr(other, 'message'):
            return self._error_list_equal(self.error_list, other.error_list)
        return (
            self.message == other.message and
            self.code == other.code and
            self.params == other.params
        )

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
