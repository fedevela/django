"Functions that help with dynamically creating decorators for views."

from functools import partial, update_wrapper, wraps


class classonlymethod(classmethod):
    def __get__(self, instance, cls=None):
        if instance is not None:
            raise AttributeError("This method is available only on the class, not on instances.")
        return super().__get__(instance, cls)


def _update_method_wrapper(_wrapper, decorator):
    # _multi_decorate()'s bound_method isn't available in this scope. Cheat by
    # using it on a dummy function.
    # Architecture contract (GUID: MDP-009): this helper owns the
    # decorator-state import boundary. The supplied decorator depends only on
    # a function-shaped probe; `_multi_decorate()` depends on this helper to
    # transfer the probe's update mappings and custom attributes onto its
    # resulting wrapper. No decorator-specific contract crosses this seam.
    @decorator
    def dummy(*args, **kwargs):
        pass
    update_wrapper(_wrapper, dummy)


def _multi_decorate(decorators, method):
    """
    Decorate `method` with one or more function decorators. `decorators` can be
    a single decorator or an iterable of decorators.
    """
    # Pseudocode contract (GUID: MDP-010):
    # VERIFIES: test_mdp_010_tuple_decorators_apply_with_existing_tuple_behavior
    # VERIFIES: test_mdp_010_tuple_decorated_method_preserves_call_semantics
    # INPUT: the supported tuple of function decorators and an instance method.
    # IF the decorator input is iterable:
    #     REVERSE its traversal order so sequential wrapping reproduces Python's
    #     existing stacked-decorator application and invocation behavior.
    # ELSE:
    #     TREAT the single decorator as a one-element application sequence.
    # WHEN the resulting method wrapper is invoked with positional and keyword
    # arguments:
    #     BIND the original method to the current instance.
    #     FOR EACH decorator in the normalized application sequence:
    #         REPLACE the current callable with that decorator's result.
    #     INVOKE the final callable with the original positional and keyword
    #     arguments, and RETURN its result without transformation.
    # IF binding, decoration, or invocation raises:
    #     PROPAGATE the exception through the existing call path unchanged.
    # Architecture contract (GUID: MDP-010): `_multi_decorate()` owns the
    # supported-tuple normalization boundary. `method_decorator()` passes the
    # decorator input through unchanged, and this private helper alone selects
    # the application sequence consumed by both the decoration-time metadata
    # probe and the invocation-local decorator chain. The bound-method adapter
    # remains downstream of normalization; positional and keyword arguments
    # cross only its existing call seam, whose result is returned directly.
    if hasattr(decorators, '__iter__'):
        # Apply a list/tuple of decorators if 'decorators' is one. Decorator
        # functions are applied so that the call order is the same as the
        # order in which they appear in the iterable.
        decorators = decorators[::-1]
    else:
        decorators = [decorators]

    def _wrapper(self, *args, **kwargs):
        # Architecture contract (GUID: MDP-005, GUID: MDP-006,
        # GUID: MDP-007, GUID: MDP-008): `_wrapper` owns the invocation-adapter
        # boundary. It depends on `method` only through normal descriptor
        # binding and exposes the resulting function-shaped callable to the
        # supplied decorators; the decorators never own or receive `self`
        # separately. Positional and keyword arguments remain opaque across
        # this boundary. The decorator chain is invocation-local, while the
        # terminal direct call is the sole caller-facing seam for both the
        # method's return value and any exception the chain leaves unhandled.
        # bound_method has the signature that 'decorator' expects i.e. no
        # 'self' argument, but it's a closure over self so it can call
        # 'func'. Also, wrap method.__get__() in a function because new
        # attributes can't be set on bound method objects, only on functions.
        # Architecture contract (GUID: MDP-001, GUID: MDP-002, GUID: MDP-004):
        # `method` owns the original metadata; this local, mutable callable is
        # the metadata transport boundary. Metadata preparation belongs after
        # adapter construction and before the existing decorator loop, which
        # remains the sole handoff seam to supplied decorators. The boundary
        # mirrors only available standard wrapper-assignment attributes, so it
        # neither depends on decorator internals nor invents absent metadata.
        bound_method = partial(method.__get__(self, type(self)))
        update_wrapper(bound_method, method)
        for dec in decorators:
            bound_method = dec(bound_method)
        return bound_method(*args, **kwargs)

    # Copy any attributes that a decorator adds to the function it decorates.
    for dec in decorators:
        _update_method_wrapper(_wrapper, dec)
    # Preserve any existing attributes of 'method', including the name.
    # Architecture contract (GUID: MDP-003, GUID: MDP-009): `_multi_decorate()`
    # owns the final metadata integration seam. The original `method` is the
    # authority for standard wrapper-assignment metadata; `_wrapper` remains
    # the owner of decorator state imported above. The final wrapper merge is
    # therefore downstream of every decorator-state import and is the single
    # boundary from which both kinds of observable state leave this module.
    update_wrapper(_wrapper, method)
    return _wrapper


def method_decorator(decorator, name=''):
    """
    Convert a function decorator into a method decorator
    """
    # 'obj' can be a class or a function. If 'obj' is a function at the time it
    # is passed to _dec,  it will eventually be a method of the class it is
    # defined on. If 'obj' is a class, the 'name' is required to be the name
    # of the method that will be decorated.
    def _dec(obj):
        if not isinstance(obj, type):
            # Integration seam (GUID: MDP-010): tuple handling belongs to
            # `_multi_decorate()`; this public adapter only routes the supplied
            # decorator contract and method into that owning boundary.
            return _multi_decorate(decorator, obj)
        if not (name and hasattr(obj, name)):
            raise ValueError(
                "The keyword argument `name` must be the name of a method "
                "of the decorated class: %s. Got '%s' instead." % (obj, name)
            )
        method = getattr(obj, name)
        if not callable(method):
            raise TypeError(
                "Cannot decorate '%s' as it isn't a callable attribute of "
                "%s (%s)." % (name, obj, method)
            )
        # Integration seam (GUID: MDP-010): class-target decoration converges
        # on the same private tuple boundary as direct method decoration.
        _wrapper = _multi_decorate(decorator, method)
        setattr(obj, name, _wrapper)
        return obj

    # Don't worry about making _dec look similar to a list/tuple as it's rather
    # meaningless.
    if not hasattr(decorator, '__iter__'):
        update_wrapper(_dec, decorator)
    # Change the name to aid debugging.
    obj = decorator if hasattr(decorator, '__name__') else decorator.__class__
    _dec.__name__ = 'method_decorator(%s)' % obj.__name__
    return _dec


def decorator_from_middleware_with_args(middleware_class):
    """
    Like decorator_from_middleware, but return a function
    that accepts the arguments to be passed to the middleware_class.
    Use like::

         cache_page = decorator_from_middleware_with_args(CacheMiddleware)
         # ...

         @cache_page(3600)
         def my_view(request):
             # ...
    """
    return make_middleware_decorator(middleware_class)


def decorator_from_middleware(middleware_class):
    """
    Given a middleware class (not an instance), return a view decorator. This
    lets you use middleware functionality on a per-view basis. The middleware
    is created with no params passed.
    """
    return make_middleware_decorator(middleware_class)()


def make_middleware_decorator(middleware_class):
    def _make_decorator(*m_args, **m_kwargs):
        def _decorator(view_func):
            middleware = middleware_class(view_func, *m_args, **m_kwargs)

            @wraps(view_func)
            def _wrapped_view(request, *args, **kwargs):
                if hasattr(middleware, 'process_request'):
                    result = middleware.process_request(request)
                    if result is not None:
                        return result
                if hasattr(middleware, 'process_view'):
                    result = middleware.process_view(request, view_func, args, kwargs)
                    if result is not None:
                        return result
                try:
                    response = view_func(request, *args, **kwargs)
                except Exception as e:
                    if hasattr(middleware, 'process_exception'):
                        result = middleware.process_exception(request, e)
                        if result is not None:
                            return result
                    raise
                if hasattr(response, 'render') and callable(response.render):
                    if hasattr(middleware, 'process_template_response'):
                        response = middleware.process_template_response(request, response)
                    # Defer running of process_response until after the template
                    # has been rendered:
                    if hasattr(middleware, 'process_response'):
                        def callback(response):
                            return middleware.process_response(request, response)
                        response.add_post_render_callback(callback)
                else:
                    if hasattr(middleware, 'process_response'):
                        return middleware.process_response(request, response)
                return response
            return _wrapped_view
        return _decorator
    return _make_decorator


def sync_and_async_middleware(func):
    """
    Mark a middleware factory as returning a hybrid middleware supporting both
    types of request.
    """
    func.sync_capable = True
    func.async_capable = True
    return func


def sync_only_middleware(func):
    """
    Mark a middleware factory as returning a sync middleware.
    This is the default.
    """
    func.sync_capable = True
    func.async_capable = False
    return func


def async_only_middleware(func):
    """Mark a middleware factory as returning an async middleware."""
    func.sync_capable = False
    func.async_capable = True
    return func
