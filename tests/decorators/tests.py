from functools import WRAPPER_ASSIGNMENTS, partial, update_wrapper, wraps
from unittest import TestCase

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import (
    login_required, permission_required, user_passes_test,
)
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.middleware.clickjacking import XFrameOptionsMiddleware
from django.test import SimpleTestCase
from django.utils.decorators import method_decorator
from django.utils.functional import keep_lazy, keep_lazy_text, lazy
from django.utils.safestring import mark_safe
from django.views.decorators.cache import (
    cache_control, cache_page, never_cache,
)
from django.views.decorators.clickjacking import (
    xframe_options_deny, xframe_options_exempt, xframe_options_sameorigin,
)
from django.views.decorators.http import (
    condition, require_GET, require_http_methods, require_POST, require_safe,
)
from django.views.decorators.vary import vary_on_cookie, vary_on_headers


def fully_decorated(request):
    """Expected __doc__"""
    return HttpResponse('<html><body>dummy</body></html>')


fully_decorated.anything = "Expected __dict__"


def compose(*functions):
    # compose(f, g)(*args, **kwargs) == f(g(*args, **kwargs))
    functions = list(reversed(functions))

    def _inner(*args, **kwargs):
        result = functions[0](*args, **kwargs)
        for f in functions[1:]:
            result = f(result)
        return result
    return _inner


full_decorator = compose(
    # django.views.decorators.http
    require_http_methods(["GET"]),
    require_GET,
    require_POST,
    require_safe,
    condition(lambda r: None, lambda r: None),

    # django.views.decorators.vary
    vary_on_headers('Accept-language'),
    vary_on_cookie,

    # django.views.decorators.cache
    cache_page(60 * 15),
    cache_control(private=True),
    never_cache,

    # django.contrib.auth.decorators
    # Apply user_passes_test twice to check #9474
    user_passes_test(lambda u: True),
    login_required,
    permission_required('change_world'),

    # django.contrib.admin.views.decorators
    staff_member_required,

    # django.utils.functional
    keep_lazy(HttpResponse),
    keep_lazy_text,
    lazy,

    # django.utils.safestring
    mark_safe,
)

fully_decorated = full_decorator(fully_decorated)


class DecoratorsTest(TestCase):

    def test_attributes(self):
        """
        Built-in decorators set certain attributes of the wrapped function.
        """
        self.assertEqual(fully_decorated.__name__, 'fully_decorated')
        self.assertEqual(fully_decorated.__doc__, 'Expected __doc__')
        self.assertEqual(fully_decorated.__dict__['anything'], 'Expected __dict__')

    def test_user_passes_test_composition(self):
        """
        The user_passes_test decorator can be applied multiple times (#9474).
        """
        def test1(user):
            user.decorators_applied.append('test1')
            return True

        def test2(user):
            user.decorators_applied.append('test2')
            return True

        def callback(request):
            return request.user.decorators_applied

        callback = user_passes_test(test1)(callback)
        callback = user_passes_test(test2)(callback)

        class DummyUser:
            pass

        class DummyRequest:
            pass

        request = DummyRequest()
        request.user = DummyUser()
        request.user.decorators_applied = []
        response = callback(request)

        self.assertEqual(response, ['test2', 'test1'])

    def test_cache_page(self):
        def my_view(request):
            return "response"
        my_view_cached = cache_page(123)(my_view)
        self.assertEqual(my_view_cached(HttpRequest()), "response")
        my_view_cached2 = cache_page(123, key_prefix="test")(my_view)
        self.assertEqual(my_view_cached2(HttpRequest()), "response")

    def test_require_safe_accepts_only_safe_methods(self):
        """
        Test for the require_safe decorator.
        A view returns either a response or an exception.
        Refs #15637.
        """
        def my_view(request):
            return HttpResponse("OK")
        my_safe_view = require_safe(my_view)
        request = HttpRequest()
        request.method = 'GET'
        self.assertIsInstance(my_safe_view(request), HttpResponse)
        request.method = 'HEAD'
        self.assertIsInstance(my_safe_view(request), HttpResponse)
        request.method = 'POST'
        self.assertIsInstance(my_safe_view(request), HttpResponseNotAllowed)
        request.method = 'PUT'
        self.assertIsInstance(my_safe_view(request), HttpResponseNotAllowed)
        request.method = 'DELETE'
        self.assertIsInstance(my_safe_view(request), HttpResponseNotAllowed)


# For testing method_decorator, a decorator that assumes a single argument.
# We will get type arguments if there is a mismatch in the number of arguments.
def simple_dec(func):
    def wrapper(arg):
        return func("test:" + arg)
    return wraps(func)(wrapper)


simple_dec_m = method_decorator(simple_dec)


# For testing method_decorator, two decorators that add an attribute to the function
def myattr_dec(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.myattr = True
    return wrapper


myattr_dec_m = method_decorator(myattr_dec)


def myattr2_dec(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.myattr2 = True
    return wrapper


myattr2_dec_m = method_decorator(myattr2_dec)


class ClsDec:
    def __init__(self, myattr):
        self.myattr = myattr

    def __call__(self, f):

        def wrapped():
            return f() and self.myattr
        return update_wrapper(wrapped, f)


class MethodDecoratorTests(SimpleTestCase):
    """
    Tests for method_decorator
    """
    def test_preserve_signature(self):
        class Test:
            @simple_dec_m
            def say(self, arg):
                return arg

        self.assertEqual("test:hello", Test().say("hello"))

    def test_preserve_attributes(self):
        # Sanity check myattr_dec and myattr2_dec
        @myattr_dec
        def func():
            pass
        self.assertIs(getattr(func, 'myattr', False), True)

        @myattr2_dec
        def func():
            pass
        self.assertIs(getattr(func, 'myattr2', False), True)

        @myattr_dec
        @myattr2_dec
        def func():
            pass

        self.assertIs(getattr(func, 'myattr', False), True)
        self.assertIs(getattr(func, 'myattr2', False), False)

        # Decorate using method_decorator() on the method.
        class TestPlain:
            @myattr_dec_m
            @myattr2_dec_m
            def method(self):
                "A method"
                pass

        # Decorate using method_decorator() on both the class and the method.
        # The decorators applied to the methods are applied before the ones
        # applied to the class.
        @method_decorator(myattr_dec_m, "method")
        class TestMethodAndClass:
            @method_decorator(myattr2_dec_m)
            def method(self):
                "A method"
                pass

        # Decorate using an iterable of function decorators.
        @method_decorator((myattr_dec, myattr2_dec), 'method')
        class TestFunctionIterable:
            def method(self):
                "A method"
                pass

        # Decorate using an iterable of method decorators.
        decorators = (myattr_dec_m, myattr2_dec_m)

        @method_decorator(decorators, "method")
        class TestMethodIterable:
            def method(self):
                "A method"
                pass

        tests = (TestPlain, TestMethodAndClass, TestFunctionIterable, TestMethodIterable)
        for Test in tests:
            with self.subTest(Test=Test):
                self.assertIs(getattr(Test().method, 'myattr', False), True)
                self.assertIs(getattr(Test().method, 'myattr2', False), True)
                self.assertIs(getattr(Test.method, 'myattr', False), True)
                self.assertIs(getattr(Test.method, 'myattr2', False), True)
                self.assertEqual(Test.method.__doc__, 'A method')
                self.assertEqual(Test.method.__name__, 'method')

    def test_new_attribute(self):
        """A decorator that sets a new attribute on the method."""
        def decorate(func):
            func.x = 1
            return func

        class MyClass:
            @method_decorator(decorate)
            def method(self):
                return True

        obj = MyClass()
        self.assertEqual(obj.method.x, 1)
        self.assertIs(obj.method(), True)

    def test_mdp_001_function_decorator_observes_all_original_wrapper_assignment_metadata(self):
        """GUID: MDP-001 - Preserve original wrapper-assignment metadata."""
        observed = {}

        def decorator(func):
            observed.update({
                attr: getattr(func, attr)
                for attr in WRAPPER_ASSIGNMENTS if hasattr(func, attr)
            })
            return func

        def method(self):
            return "result"

        metadata_values = {
            "__module__": "original module",
            "__name__": "original_name",
            "__qualname__": "original_qualname",
            "__doc__": "original doc",
            "__annotations__": {"return": "original annotation"},
            "__type_params__": ("original type parameter",),
        }
        metadata = {
            attr: metadata_values[attr] for attr in WRAPPER_ASSIGNMENTS
        }
        for attr in WRAPPER_ASSIGNMENTS:
            setattr(method, attr, metadata[attr])

        decorated_method = method_decorator(decorator)(method)

        class Test:
            method = decorated_method

        observed.clear()
        self.assertEqual(Test().method(), "result")
        self.assertEqual(observed, metadata)

    def test_mdp_002_wraps_decorator_invocation_avoids_missing_metadata_attribute_error(self):
        """GUID: MDP-002 - Invoke a wraps-based decorator without metadata errors."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            if isinstance(func, partial):
                for attr in WRAPPER_ASSIGNMENTS:
                    getattr(wrapper, attr)
            return wrapper

        def method(self):
            return "result"

        if "__type_params__" in WRAPPER_ASSIGNMENTS:
            method.__type_params__ = ("original type parameter",)
        decorated_method = method_decorator(decorator)(method)

        class Test:
            method = decorated_method

        self.assertEqual(Test().method(), "result")

    def test_mdp_003_original_wrapper_assignment_metadata_remains_on_resulting_method(self):
        """GUID: MDP-003 - Retain original standard wrapper-assignment metadata."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            for attr in WRAPPER_ASSIGNMENTS:
                setattr(wrapper, attr, decorator_metadata[attr])
            return wrapper

        def method(self):
            return "result"

        metadata_values = {
            "__module__": "original module",
            "__name__": "original_name",
            "__qualname__": "original_qualname",
            "__doc__": "original doc",
            "__annotations__": {"return": "original annotation"},
            "__type_params__": ("original type parameter",),
        }
        decorator_metadata_values = {
            "__module__": "decorator module",
            "__name__": "decorator_name",
            "__qualname__": "decorator_qualname",
            "__doc__": "decorator doc",
            "__annotations__": {"return": "decorator annotation"},
            "__type_params__": ("decorator type parameter",),
        }
        metadata = {
            attr: metadata_values[attr] for attr in WRAPPER_ASSIGNMENTS
        }
        decorator_metadata = {
            attr: decorator_metadata_values[attr] for attr in WRAPPER_ASSIGNMENTS
        }
        for attr, value in metadata.items():
            setattr(method, attr, value)

        decorated_method = method_decorator(decorator)(method)

        self.assertEqual(
            {attr: getattr(decorated_method, attr) for attr in WRAPPER_ASSIGNMENTS},
            metadata,
        )
        self.assertIs(decorated_method.__wrapped__, method)

    def test_mdp_004_missing_optional_wrapper_metadata_allows_adaptation_and_invocation(self):
        """GUID: MDP-004 - Tolerate absent optional wrapper metadata."""
        class CallableWithoutMetadata:
            def __call__(self, instance):
                return "result"

            def __get__(self, instance, cls=None):
                if instance is None:
                    return self
                return partial(self, instance)

        original = CallableWithoutMetadata()
        missing = [
            attr for attr in WRAPPER_ASSIGNMENTS if not hasattr(original, attr)
        ]
        self.assertTrue(missing)
        observed_missing = set()

        def decorator(func):
            observed_missing.update(
                attr for attr in missing if not hasattr(func, attr)
            )
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        class Test:
            method = method_decorator(decorator)(original)

        self.assertEqual(Test().method(), "result")
        self.assertEqual(observed_missing, set(missing))

    def test_mdp_005_bound_instance_and_supplied_arguments_are_delivered_unchanged(self):
        """GUID: MDP-005 - Preserve binding and argument delivery."""
        observed = []

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        class Test:
            @method_decorator(decorator)
            def method(self, *args, **kwargs):
                observed.append((self, args, kwargs))

        instance = Test()
        positional = (object(), object())
        keyword_value = object()

        instance.method(*positional, keyword=keyword_value)

        self.assertEqual(len(observed), 1)
        bound_instance, received_args, received_kwargs = observed[0]
        self.assertIs(bound_instance, instance)
        self.assertEqual(received_args, positional)
        self.assertEqual(received_kwargs, {"keyword": keyword_value})
        self.assertIs(received_args[0], positional[0])
        self.assertIs(received_args[1], positional[1])
        self.assertIs(received_kwargs["keyword"], keyword_value)

    def test_mdp_006_original_return_value_is_delivered_unchanged(self):
        """GUID: MDP-006 - Preserve the original return value."""
        expected = object()

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        class Test:
            @method_decorator(decorator)
            def method(self):
                return expected

        self.assertIs(Test().method(), expected)

    def test_mdp_007_unhandled_exception_remains_observable_unchanged(self):
        """GUID: MDP-007 - Preserve an unhandled exception for the caller."""
        class DistinguishableError(Exception):
            pass

        expected = DistinguishableError("expected exception")

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        class Test:
            @method_decorator(decorator)
            def method(self):
                raise expected

        with self.assertRaises(DistinguishableError) as captured:
            Test().method()

        self.assertIs(captured.exception, expected)

    def test_mdp_008_decorator_executes_once_for_every_method_invocation(self):
        """GUID: MDP-008 - Execute the decorator once per invocation."""
        executions = 0

        def decorator(func):
            nonlocal executions
            executions += 1

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper

        class Test:
            @method_decorator(decorator)
            def method(self):
                pass

        # Ignore method_decorator()'s decoration-time metadata probe. This
        # requirement concerns applying the decorator to each runtime call.
        executions = 0
        instance = Test()

        for expected_executions in range(1, 4):
            instance.method()
            self.assertEqual(executions, expected_executions)

    def test_mdp_009_decorator_custom_attribute_and_value_remain_on_resulting_method(self):
        """GUID: MDP-009 - Preserve a decorator-produced custom attribute and value."""
        custom_value = object()

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            wrapper.decorator_attribute = custom_value
            return wrapper

        class Test:
            @method_decorator(decorator)
            def method(self):
                return "result"

        self.assertIs(Test.method.decorator_attribute, custom_value)
        self.assertIs(Test().method.decorator_attribute, custom_value)
        self.assertEqual(Test().method(), "result")

    def test_mdp_009_decorator_wrapper_updates_remain_on_resulting_method(self):
        """GUID: MDP-009 - Preserve decorator-produced wrapper updates."""
        update_value = object()

        def decorator(func):
            func.decorator_update = update_value

            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return update_wrapper(wrapper, func, assigned=())

        class Test:
            @method_decorator(decorator)
            def method(self):
                return "result"

        self.assertIs(Test.method.decorator_update, update_value)
        self.assertIs(Test().method.decorator_update, update_value)
        self.assertEqual(Test().method(), "result")

    def test_bad_iterable(self):
        decorators = {myattr_dec_m, myattr2_dec_m}
        msg = "'set' object is not subscriptable"
        with self.assertRaisesMessage(TypeError, msg):
            @method_decorator(decorators, "method")
            class TestIterable:
                def method(self):
                    "A method"
                    pass

    # Test for argumented decorator
    def test_argumented(self):
        class Test:
            @method_decorator(ClsDec(False))
            def method(self):
                return True

        self.assertIs(Test().method(), False)

    def test_descriptors(self):

        def original_dec(wrapped):
            def _wrapped(arg):
                return wrapped(arg)

            return _wrapped

        method_dec = method_decorator(original_dec)

        class bound_wrapper:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.__name__ = wrapped.__name__

            def __call__(self, arg):
                return self.wrapped(arg)

            def __get__(self, instance, cls=None):
                return self

        class descriptor_wrapper:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.__name__ = wrapped.__name__

            def __get__(self, instance, cls=None):
                return bound_wrapper(self.wrapped.__get__(instance, cls))

        class Test:
            @method_dec
            @descriptor_wrapper
            def method(self, arg):
                return arg

        self.assertEqual(Test().method(1), 1)

    def test_class_decoration(self):
        """
        @method_decorator can be used to decorate a class and its methods.
        """
        def deco(func):
            def _wrapper(*args, **kwargs):
                return True
            return _wrapper

        @method_decorator(deco, name="method")
        class Test:
            def method(self):
                return False

        self.assertTrue(Test().method())

    def test_mdp_011_class_level_named_callable_decoration_succeeds_and_preserves_invocation(self):
        """
        GUID: MDP-011 - Given a class with the requested callable method, class-level
        decoration succeeds and an instance can invoke the decorated method with
        existing call semantics.
        """
        calls = []
        result = object()

        def decorator(func):
            @wraps(func)
            def _wrapper(*args, **kwargs):
                calls.append((args, kwargs))
                return func(*args, **kwargs)
            return _wrapper

        @method_decorator(decorator, name="method")
        class Test:
            def method(self, arg, *, option):
                calls.append((arg, option))
                return result

        instance = Test()
        positional = object()
        keyword = object()

        self.assertIs(instance.method(positional, option=keyword), result)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], (positional,))
        self.assertEqual(calls[0][1], {"option": keyword})
        self.assertEqual(calls[1], (positional, keyword))

    def test_tuple_of_decorators(self):
        """
        @method_decorator can accept a tuple of decorators.
        """
        def add_question_mark(func):
            def _wrapper(*args, **kwargs):
                return func(*args, **kwargs) + "?"
            return _wrapper

        def add_exclamation_mark(func):
            def _wrapper(*args, **kwargs):
                return func(*args, **kwargs) + "!"
            return _wrapper

        # The order should be consistent with the usual order in which
        # decorators are applied, e.g.
        #    @add_exclamation_mark
        #    @add_question_mark
        #    def func():
        #        ...
        decorators = (add_exclamation_mark, add_question_mark)

        @method_decorator(decorators, name="method")
        class TestFirst:
            def method(self):
                return "hello world"

        class TestSecond:
            @method_decorator(decorators)
            def method(self):
                return "hello world"

        self.assertEqual(TestFirst().method(), "hello world?!")
        self.assertEqual(TestSecond().method(), "hello world?!")

    def test_mdp_010_tuple_decorators_apply_with_existing_tuple_behavior(self):
        """
        GUID: MDP-010 - Apply every decorator using existing tuple behavior.
        """
        calls = []

        def record_call(name):
            def decorator(func):
                def _wrapper(*args, **kwargs):
                    calls.append('%s before' % name)
                    result = func(*args, **kwargs)
                    calls.append('%s after' % name)
                    return result
                return _wrapper
            return decorator

        decorators = (record_call('first'), record_call('second'))

        class Test:
            @method_decorator(decorators)
            def method(self):
                calls.append('method')

        Test().method()

        self.assertEqual(calls, [
            'first before',
            'second before',
            'method',
            'second after',
            'first after',
        ])

    def test_mdp_010_tuple_decorated_method_preserves_call_semantics(self):
        """
        GUID: MDP-010 - Preserve positional arguments, keyword arguments, and return value.
        """
        calls = []
        result = object()

        def record_call(name):
            def decorator(func):
                def _wrapper(*args, **kwargs):
                    calls.append((name, args, kwargs))
                    return func(*args, **kwargs)
                return _wrapper
            return decorator

        positional = object()
        keyword = object()

        class Test:
            @method_decorator((record_call('first'), record_call('second')))
            def method(self, arg, *, option):
                calls.append(('method', (arg,), {'option': option}))
                return result

        actual_result = Test().method(positional, option=keyword)

        self.assertIs(actual_result, result)
        self.assertEqual([name for name, args, kwargs in calls], [
            'first', 'second', 'method',
        ])
        for name, args, kwargs in calls:
            self.assertIs(args[0], positional)
            self.assertIs(kwargs['option'], keyword)

    def test_invalid_non_callable_attribute_decoration(self):
        """
        @method_decorator on a non-callable attribute raises an error.
        """
        msg = (
            "Cannot decorate 'prop' as it isn't a callable attribute of "
            "<class 'Test'> (1)"
        )
        with self.assertRaisesMessage(TypeError, msg):
            @method_decorator(lambda: None, name="prop")
            class Test:
                prop = 1

                @classmethod
                def __module__(cls):
                    return "tests"

    def test_mdp_012_non_callable_named_attribute_error_remains_observable(self):
        """
        GUID: MDP-012 - Given a class whose requested named attribute is not
        callable, class-level decoration leaves the established error observable.
        """
        def decorator(func):
            self.fail("The decorator must not run for a non-callable attribute.")

        msg = (
            "Cannot decorate 'prop' as it isn't a callable attribute of "
            "<class 'Test'> (1)"
        )
        with self.assertRaisesMessage(TypeError, msg):
            @method_decorator(decorator, name="prop")
            class Test:
                prop = 1

                @classmethod
                def __module__(cls):
                    return "tests"

    def test_invalid_method_name_to_decorate(self):
        """
        @method_decorator on a nonexistent method raises an error.
        """
        msg = (
            "The keyword argument `name` must be the name of a method of the "
            "decorated class: <class 'Test'>. Got 'nonexistent_method' instead"
        )
        with self.assertRaisesMessage(ValueError, msg):
            @method_decorator(lambda: None, name='nonexistent_method')
            class Test:
                @classmethod
                def __module__(cls):
                    return "tests"

    def test_mdp_012_missing_named_method_error_remains_observable(self):
        """
        GUID: MDP-012 - Given a class without the requested method name,
        class-level decoration leaves the established error observable.
        """
        def decorator(func):
            self.fail("The decorator must not run for a missing method.")

        msg = (
            "The keyword argument `name` must be the name of a method of the "
            "decorated class: <class 'Test'>. Got 'missing' instead"
        )
        with self.assertRaisesMessage(ValueError, msg):
            @method_decorator(decorator, name="missing")
            class Test:
                @classmethod
                def __module__(cls):
                    return "tests"


class XFrameOptionsDecoratorsTests(TestCase):
    """
    Tests for the X-Frame-Options decorators.
    """
    def test_deny_decorator(self):
        """
        Ensures @xframe_options_deny properly sets the X-Frame-Options header.
        """
        @xframe_options_deny
        def a_view(request):
            return HttpResponse()
        r = a_view(HttpRequest())
        self.assertEqual(r.headers['X-Frame-Options'], 'DENY')

    def test_sameorigin_decorator(self):
        """
        Ensures @xframe_options_sameorigin properly sets the X-Frame-Options
        header.
        """
        @xframe_options_sameorigin
        def a_view(request):
            return HttpResponse()
        r = a_view(HttpRequest())
        self.assertEqual(r.headers['X-Frame-Options'], 'SAMEORIGIN')

    def test_exempt_decorator(self):
        """
        Ensures @xframe_options_exempt properly instructs the
        XFrameOptionsMiddleware to NOT set the header.
        """
        @xframe_options_exempt
        def a_view(request):
            return HttpResponse()
        req = HttpRequest()
        resp = a_view(req)
        self.assertIsNone(resp.get('X-Frame-Options', None))
        self.assertTrue(resp.xframe_options_exempt)

        # Since the real purpose of the exempt decorator is to suppress
        # the middleware's functionality, let's make sure it actually works...
        r = XFrameOptionsMiddleware(a_view)(req)
        self.assertIsNone(r.get('X-Frame-Options', None))


class NeverCacheDecoratorTest(SimpleTestCase):
    def test_never_cache_decorator(self):
        @never_cache
        def a_view(request):
            return HttpResponse()
        r = a_view(HttpRequest())
        self.assertEqual(
            set(r.headers['Cache-Control'].split(', ')),
            {'max-age=0', 'no-cache', 'no-store', 'must-revalidate', 'private'},
        )

    def test_never_cache_decorator_http_request(self):
        class MyClass:
            @never_cache
            def a_view(self, request):
                return HttpResponse()
        msg = (
            "never_cache didn't receive an HttpRequest. If you are decorating "
            "a classmethod, be sure to use @method_decorator."
        )
        with self.assertRaisesMessage(TypeError, msg):
            MyClass().a_view(HttpRequest())


class CacheControlDecoratorTest(SimpleTestCase):
    def test_cache_control_decorator_http_request(self):
        class MyClass:
            @cache_control(a='b')
            def a_view(self, request):
                return HttpResponse()

        msg = (
            "cache_control didn't receive an HttpRequest. If you are "
            "decorating a classmethod, be sure to use @method_decorator."
        )
        with self.assertRaisesMessage(TypeError, msg):
            MyClass().a_view(HttpRequest())
