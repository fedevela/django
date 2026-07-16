import inspect
import types
from collections import defaultdict
from itertools import chain

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


# DBTABLE-001 architecture contract:
# - Ownership: check_all_models() owns both managed-table collision collection
#   and the diagnostic emitted for each collision.
# - Input boundary: app_configs selects the models; settings.DATABASE_ROUTERS
#   is the only router-configuration input needed at the diagnostic seam.
# - Dependency direction: model checks may read router configuration, but must
#   not instantiate or call database routers to preserve this no-router path.
# - Integration seam: retain the shared db_table_models collector for same-app
#   and cross-app models, and guard the models.E028 branch where collisions are
#   converted to CheckMessage instances.
# - Verification home: DBTable001NoDatabaseRoutersContractTests in
#   tests/check_framework/test_model_checks.py covers all DBTABLE-001 paths.
# DBTABLE-002, DBTABLE-003, and DBTABLE-004 architecture contract:
# - Ownership: check_all_models() owns routed-table collision diagnostics; no
#   router-specific model or application layer owns either collision variant.
# - Input boundary: the existing db_table_models groups supply the shared table
#   and complete model-label set, while settings.DATABASE_ROUTERS supplies only
#   the fact that routing is configured.
# - Diagnostic contract: a routed collision produces one non-blocking
#   CheckMessage that carries the shared table, every conflicting model label,
#   and guidance to verify that routing separates the models. Its identifier is
#   intentionally left to implementation.
# - Dependency direction: model checks depend on router configuration and the
#   checks message abstraction; they must not instantiate or invoke routers or
#   attempt to prove model isolation.
# - Integration seam: extend the existing collision-to-models.E028 branch in
#   the db_table_models loop. Same-app (DBTABLE-003) and cross-app (DBTABLE-002)
#   groups enter the same seam; DBTABLE-004 defines its diagnostic payload.
# - Verification home: RoutedDuplicateDBTableContractTests in
#   tests/check_framework/test_model_checks.py covers the routed output contract.
# DBTABLE-005 architecture contract:
# - Ownership: check_all_models() retains ownership of model selection,
#   duplicate-table eligibility, model.check() delegation, and index and
#   constraint collision checks; routed diagnostics introduce no new owner.
# - Boundary: the managed, non-proxy guard encloses only insertion into the
#   db_table_models collector. Abstract-model selection remains upstream in the
#   application registry, while proxy and unmanaged models continue through the
#   pre-existing model.check(), index, and constraint paths.
# - Dependency direction: settings.DATABASE_ROUTERS may select a diagnostic only
#   after duplicate-table groups are collected; model selection, grouping
#   eligibility, and unrelated check results must not depend on router state.
# - Integration seam: routed behavior is confined to the existing
#   db_table_models diagnostic branch. The model iteration and the independent
#   index and constraint collectors remain structurally unchanged.
# - Verification home: DBTable005UnaffectedModelCheckOutcomesContractTests in
#   tests/check_framework/test_model_checks.py traces the abstract, proxy,
#   unmanaged, and unrelated-check preservation obligations.
@register(Tags.models)
def check_all_models(app_configs=None, **kwargs):
    db_table_models = defaultdict(list)
    indexes = defaultdict(list)
    constraints = defaultdict(list)
    errors = []
    if app_configs is None:
        models = apps.get_models()
    else:
        models = chain.from_iterable(app_config.get_models() for app_config in app_configs)
    # DBTABLE-001 logic obligation:
    # INPUT: the models selected for system checks and the configured database
    # routers.
    # FOR EACH selected model:
    #   IF the model is managed and is not a proxy, group its label by db_table;
    #   application boundaries do not change this grouping decision.
    # AFTER grouping:
    #   FOR EACH db_table whose group contains more than one model label:
    #     IF no database routers are configured, append models.E028 for that
    #     db_table and include every colliding label in the diagnostic.
    #     OTHERWISE, leave routed-duplicate handling outside DBTABLE-001.
    # OUTPUT: preserve the accumulated model-check errors, including E028 for
    # duplicate managed tables both within one app and across different apps.
    # DBTABLE-005 unaffected-outcome logic obligation:
    # INPUT: use the existing model selection above without adding abstract
    # models or otherwise changing which models enter the system-check pass.
    # FOR EACH selected model:
    #   IF it is managed and is not a proxy, include it in duplicate-table
    #   grouping; OTHERWISE, skip only that grouping step so unmanaged and proxy
    #   models retain their existing no-collision outcome.
    #   REGARDLESS of duplicate-table eligibility, execute the pre-existing
    #   overridden-check validation, model.check() handoff, and index and
    #   constraint collection in their current order.
    #   IF check() is not an inherited class method, append the existing E020;
    #   OTHERWISE, append every result returned by model.check() unchanged.
    # AFTER grouping, allow router configuration to select the diagnostic only
    # for an actual duplicate-table group; it must not alter model selection,
    # grouping eligibility, or any model.check() result.
    # THEN evaluate index and constraint collisions from their independent
    # collectors with the existing identifiers, messages, and ordering.
    # OUTPUT: return the same abstract, proxy, unmanaged, and unrelated-check
    # outcomes that this flow would produce without routed-duplicate handling.
    for model in models:
        if model._meta.managed and not model._meta.proxy:
            db_table_models[model._meta.db_table].append(model._meta.label)
        if not inspect.ismethod(model.check):
            errors.append(
                Error(
                    "The '%s.check()' class method is currently overridden by %r."
                    % (model.__name__, model.check),
                    obj=model,
                    id='models.E020'
                )
            )
        else:
            errors.extend(model.check(**kwargs))
        for model_index in model._meta.indexes:
            indexes[model_index.name].append(model._meta.label)
        for model_constraint in model._meta.constraints:
            constraints[model_constraint.name].append(model._meta.label)
    if settings.DATABASE_ROUTERS:
        error_class, error_id = Warning, 'models.W035'
        error_hint = (
            'You have configured settings.DATABASE_ROUTERS. Verify that %s '
            'are correctly routed to separate databases.'
        )
    else:
        error_class, error_id = Error, 'models.E028'
        error_hint = None
    for db_table, model_labels in db_table_models.items():
        # DBTABLE-002 and DBTABLE-003 logic obligations:
        # INPUT: one shared db_table and all managed, non-proxy model labels
        # collected for it, plus the configured database-router setting.
        # IF fewer than two model labels share the table, emit no duplicate-table
        # diagnostic and continue with the next table.
        # IF two or more labels share the table AND routers are not configured,
        # preserve the blocking models.E028 path below.
        # IF two or more labels share the table AND routers are configured, emit
        # a non-blocking diagnostic instead of models.E028; apply this branch
        # identically whether the labels belong to one application (DBTABLE-003)
        # or to different applications (DBTABLE-002).
        # DBTABLE-004 diagnostic-content obligation for the routed branch:
        # BUILD the diagnostic from the shared db_table and the complete list of
        # conflicting model labels, without attempting to execute or prove router
        # behavior.
        # INCLUDE guidance that the user must verify database routing separates
        # the conflicting models.
        # OUTPUT: append exactly the selected duplicate-table diagnostic and then
        # continue checking other tables; router uncertainty remains advisory and
        # must not become models.E028 or silently suppress the collision.
        if len(model_labels) != 1:
            model_labels_str = ', '.join(model_labels)
            errors.append(
                error_class(
                    "db_table '%s' is used by multiple models: %s."
                    % (db_table, model_labels_str),
                    obj=db_table,
                    hint=(error_hint % model_labels_str) if error_hint else None,
                    id=error_id,
                )
            )
    for index_name, model_labels in indexes.items():
        if len(model_labels) > 1:
            model_labels = set(model_labels)
            errors.append(
                Error(
                    "index name '%s' is not unique %s %s." % (
                        index_name,
                        'for model' if len(model_labels) == 1 else 'amongst models:',
                        ', '.join(sorted(model_labels)),
                    ),
                    id='models.E029' if len(model_labels) == 1 else 'models.E030',
                ),
            )
    for constraint_name, model_labels in constraints.items():
        if len(model_labels) > 1:
            model_labels = set(model_labels)
            errors.append(
                Error(
                    "constraint name '%s' is not unique %s %s." % (
                        constraint_name,
                        'for model' if len(model_labels) == 1 else 'amongst models:',
                        ', '.join(sorted(model_labels)),
                    ),
                    id='models.E031' if len(model_labels) == 1 else 'models.E032',
                ),
            )
    return errors


def _check_lazy_references(apps, ignore=None):
    """
    Ensure all lazy (i.e. string) model references have been resolved.

    Lazy references are used in various places throughout Django, primarily in
    related fields and model signals. Identify those common cases and provide
    more helpful error messages for them.

    The ignore parameter is used by StateApps to exclude swappable models from
    this check.
    """
    pending_models = set(apps._pending_operations) - (ignore or set())

    # Short circuit if there aren't any errors.
    if not pending_models:
        return []

    from django.db.models import signals
    model_signals = {
        signal: name for name, signal in vars(signals).items()
        if isinstance(signal, signals.ModelSignal)
    }

    def extract_operation(obj):
        """
        Take a callable found in Apps._pending_operations and identify the
        original callable passed to Apps.lazy_model_operation(). If that
        callable was a partial, return the inner, non-partial function and
        any arguments and keyword arguments that were supplied with it.

        obj is a callback defined locally in Apps.lazy_model_operation() and
        annotated there with a `func` attribute so as to imitate a partial.
        """
        operation, args, keywords = obj, [], {}
        while hasattr(operation, 'func'):
            args.extend(getattr(operation, 'args', []))
            keywords.update(getattr(operation, 'keywords', {}))
            operation = operation.func
        return operation, args, keywords

    def app_model_error(model_key):
        try:
            apps.get_app_config(model_key[0])
            model_error = "app '%s' doesn't provide model '%s'" % model_key
        except LookupError:
            model_error = "app '%s' isn't installed" % model_key[0]
        return model_error

    # Here are several functions which return CheckMessage instances for the
    # most common usages of lazy operations throughout Django. These functions
    # take the model that was being waited on as an (app_label, modelname)
    # pair, the original lazy function, and its positional and keyword args as
    # determined by extract_operation().

    def field_error(model_key, func, args, keywords):
        error_msg = (
            "The field %(field)s was declared with a lazy reference "
            "to '%(model)s', but %(model_error)s."
        )
        params = {
            'model': '.'.join(model_key),
            'field': keywords['field'],
            'model_error': app_model_error(model_key),
        }
        return Error(error_msg % params, obj=keywords['field'], id='fields.E307')

    def signal_connect_error(model_key, func, args, keywords):
        error_msg = (
            "%(receiver)s was connected to the '%(signal)s' signal with a "
            "lazy reference to the sender '%(model)s', but %(model_error)s."
        )
        receiver = args[0]
        # The receiver is either a function or an instance of class
        # defining a `__call__` method.
        if isinstance(receiver, types.FunctionType):
            description = "The function '%s'" % receiver.__name__
        elif isinstance(receiver, types.MethodType):
            description = "Bound method '%s.%s'" % (receiver.__self__.__class__.__name__, receiver.__name__)
        else:
            description = "An instance of class '%s'" % receiver.__class__.__name__
        signal_name = model_signals.get(func.__self__, 'unknown')
        params = {
            'model': '.'.join(model_key),
            'receiver': description,
            'signal': signal_name,
            'model_error': app_model_error(model_key),
        }
        return Error(error_msg % params, obj=receiver.__module__, id='signals.E001')

    def default_error(model_key, func, args, keywords):
        error_msg = "%(op)s contains a lazy reference to %(model)s, but %(model_error)s."
        params = {
            'op': func,
            'model': '.'.join(model_key),
            'model_error': app_model_error(model_key),
        }
        return Error(error_msg % params, obj=func, id='models.E022')

    # Maps common uses of lazy operations to corresponding error functions
    # defined above. If a key maps to None, no error will be produced.
    # default_error() will be used for usages that don't appear in this dict.
    known_lazy = {
        ('django.db.models.fields.related', 'resolve_related_class'): field_error,
        ('django.db.models.fields.related', 'set_managed'): None,
        ('django.dispatch.dispatcher', 'connect'): signal_connect_error,
    }

    def build_error(model_key, func, args, keywords):
        key = (func.__module__, func.__name__)
        error_fn = known_lazy.get(key, default_error)
        return error_fn(model_key, func, args, keywords) if error_fn else None

    return sorted(filter(None, (
        build_error(model_key, *extract_operation(func))
        for model_key in pending_models
        for func in apps._pending_operations[model_key]
    )), key=lambda error: error.msg)


@register(Tags.models)
def check_lazy_references(app_configs=None, **kwargs):
    return _check_lazy_references(apps)
