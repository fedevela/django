"""
Various data structures used in query construction.

Factored out from django.db.models.query to avoid making the main module very
large and/or so that they can be used by other modules without getting into
circular import difficulties.
"""
import functools
import inspect
from collections import namedtuple

from django.core.exceptions import FieldError
from django.db.models.constants import LOOKUP_SEP
from django.utils import tree

# PathInfo is used when converting lookups (fk__somecol). The contents
# describe the relation in Model terms (model Options and Fields for both
# sides of the relation. The join_field is the field backing the relation.
PathInfo = namedtuple('PathInfo', 'from_opts to_opts target_fields join_field m2m direct filtered_relation')


def subclasses(cls):
    yield cls
    for subclass in cls.__subclasses__():
        yield from subclasses(subclass)


class Q(tree.Node):
    """
    Encapsulate filters as objects that can then be combined logically (using
    `&` and `|`).
    """
    # Connection types
    AND = 'AND'
    OR = 'OR'
    default = AND
    conditional = True

    def __init__(self, *args, _connector=None, _negated=False, **kwargs):
        super().__init__(children=[*args, *sorted(kwargs.items())], connector=_connector, negated=_negated)

    def _combine(self, other, conn):
        # QCOMB-001/QCOMB-002/QCOMB-003/QCOMB-005/QCOMB-006 architecture:
        # This method owns the empty-operand identity seam. Its structural-copy
        # boundary is the inherited Node._new_instance() factory, supplied with
        # the surviving Q's children, connector, and negated state. Node owns
        # allocating an independent children container; Q owns selecting the
        # survivor. Leaf lookup values remain opaque references across this
        # boundary, so the seam must not depend on deepcopy or serialization.
        # QCOMB-004/QCOMB-007 architecture:
        # Q.__or__ owns OR-connector selection; this method owns combination
        # topology and the empty-operand compatibility boundary. For two
        # non-empty operands it delegates child placement, in operand order,
        # to the inherited Node.add() contract. Query compilation remains the
        # downstream consumer of the resulting Q tree, while condition values
        # stay opaque to this boundary. Thus dependency points from Q's public
        # operator seam through _combine() to Node's tree contract, without a
        # serialization, lookup-resolution, or evaluation dependency here.
        # QCOMB-008 architecture:
        # This existing empty-operand branch is the production ownership and
        # integration seam for both supported OR operand orders. It selects the
        # non-empty Q and delegates allocation of the identity-like result to
        # Node._new_instance(), whose children-list copy is the structural
        # boundary. The x__in leaf and its dict_keys value remain opaque,
        # reference-preserved children of that copied container. Regression
        # ownership remains in QTests beside the established Q combination
        # coverage; no lookup, pickle, or query-compiler dependency belongs on
        # this seam.
        # QCOMB-001/QCOMB-002/QCOMB-003/QCOMB-005/QCOMB-006 pseudocode:
        # INPUT: the left Q (`self`), the proposed right operand, and connector.
        # IF the right operand is not a Q, follow the existing type-error path
        # before inspecting, copying, or otherwise processing either operand.
        # IF connector is OR and either Q is empty:
        #     SELECT the non-empty Q as the survivor; when both are empty,
        #     preserve the established operand-order choice.
        #     CREATE an independent structural result from the survivor's Q
        #     state and children container, retaining each condition and its
        #     contained value by reference rather than serializing, pickling,
        #     or recursively copying those accepted values.  [QCOMB-001/002/006]
        #     RETURN the result without changing either operand, either
        #     operand's child container, or any contained value.  [QCOMB-003/005]
        # OTHERWISE continue through the established non-empty combination
        # flow; failures from that flow are outside this empty-OR obligation.
        # QCOMB-004/QCOMB-007 pseudocode:
        # INPUT: two Q operands and the OR connector supplied by Q.__or__().
        # IF either operand is empty:
        #     RETURN the established structural result selected above: a copy
        #     of the non-empty operand, or the established left-operand result
        #     when both operands are empty.  [QCOMB-007]
        # ELSE both operands are non-empty:
        #     CREATE a fresh Q combination node and set its connector to OR.
        #     ADD the left condition tree, then the right condition tree, using
        #     the established node-combination rules so both distinct
        #     conditions remain represented as logical alternatives.
        #     PRESERVE accepted condition values, including pickleable values,
        #     and preserve the established connector and condition structure;
        #     do not introduce serialization or value transformation.
        #     RETURN the OR node for the existing query-evaluation handoff.
        #     [QCOMB-004/QCOMB-007]
        # FAILURE: reject a non-Q operand through the established TypeError
        # path before either empty or non-empty combination processing.
        if not isinstance(other, Q):
            raise TypeError(other)

        # If the other Q() is empty, ignore it and just use `self`.
        if not other:
            return self._new_instance(self.children, self.connector, self.negated)
        # Or if this Q is empty, ignore it and just use `other`.
        elif not self:
            return other._new_instance(other.children, other.connector, other.negated)

        obj = type(self)()
        obj.connector = conn
        obj.add(self, conn)
        obj.add(other, conn)
        return obj

    def __or__(self, other):
        return self._combine(other, self.OR)

    def __and__(self, other):
        return self._combine(other, self.AND)

    def __invert__(self):
        obj = type(self)()
        obj.add(self, self.AND)
        obj.negate()
        return obj

    def resolve_expression(self, query=None, allow_joins=True, reuse=None, summarize=False, for_save=False):
        # We must promote any new joins to left outer joins so that when Q is
        # used as an expression, rows aren't filtered due to joins.
        clause, joins = query._add_q(
            self, reuse, allow_joins=allow_joins, split_subq=False,
            check_filterable=False,
        )
        query.promote_joins(joins)
        return clause

    def deconstruct(self):
        path = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
        if path.startswith('django.db.models.query_utils'):
            path = path.replace('django.db.models.query_utils', 'django.db.models')
        args, kwargs = (), {}
        if len(self.children) == 1 and not isinstance(self.children[0], Q):
            child = self.children[0]
            kwargs = {child[0]: child[1]}
        else:
            args = tuple(self.children)
            if self.connector != self.default:
                kwargs = {'_connector': self.connector}
        if self.negated:
            kwargs['_negated'] = True
        return path, args, kwargs


class DeferredAttribute:
    """
    A wrapper for a deferred-loading field. When the value is read from this
    object the first time, the query is executed.
    """
    def __init__(self, field):
        self.field = field

    def __get__(self, instance, cls=None):
        """
        Retrieve and caches the value from the datastore on the first lookup.
        Return the cached value.
        """
        if instance is None:
            return self
        data = instance.__dict__
        field_name = self.field.attname
        if field_name not in data:
            # Let's see if the field is part of the parent chain. If so we
            # might be able to reuse the already loaded value. Refs #18343.
            val = self._check_parent_chain(instance)
            if val is None:
                instance.refresh_from_db(fields=[field_name])
            else:
                data[field_name] = val
        return data[field_name]

    def _check_parent_chain(self, instance):
        """
        Check if the field value can be fetched from a parent field already
        loaded in the instance. This can be done if the to-be fetched
        field is a primary key field.
        """
        opts = instance._meta
        link_field = opts.get_ancestor_link(self.field.model)
        if self.field.primary_key and self.field != link_field:
            return getattr(instance, link_field.attname)
        return None


class RegisterLookupMixin:

    @classmethod
    def _get_lookup(cls, lookup_name):
        return cls.get_lookups().get(lookup_name, None)

    @classmethod
    @functools.lru_cache(maxsize=None)
    def get_lookups(cls):
        class_lookups = [parent.__dict__.get('class_lookups', {}) for parent in inspect.getmro(cls)]
        return cls.merge_dicts(class_lookups)

    def get_lookup(self, lookup_name):
        from django.db.models.lookups import Lookup
        found = self._get_lookup(lookup_name)
        if found is None and hasattr(self, 'output_field'):
            return self.output_field.get_lookup(lookup_name)
        if found is not None and not issubclass(found, Lookup):
            return None
        return found

    def get_transform(self, lookup_name):
        from django.db.models.lookups import Transform
        found = self._get_lookup(lookup_name)
        if found is None and hasattr(self, 'output_field'):
            return self.output_field.get_transform(lookup_name)
        if found is not None and not issubclass(found, Transform):
            return None
        return found

    @staticmethod
    def merge_dicts(dicts):
        """
        Merge dicts in reverse to preference the order of the original list. e.g.,
        merge_dicts([a, b]) will preference the keys in 'a' over those in 'b'.
        """
        merged = {}
        for d in reversed(dicts):
            merged.update(d)
        return merged

    @classmethod
    def _clear_cached_lookups(cls):
        for subclass in subclasses(cls):
            subclass.get_lookups.cache_clear()

    @classmethod
    def register_lookup(cls, lookup, lookup_name=None):
        if lookup_name is None:
            lookup_name = lookup.lookup_name
        if 'class_lookups' not in cls.__dict__:
            cls.class_lookups = {}
        cls.class_lookups[lookup_name] = lookup
        cls._clear_cached_lookups()
        return lookup

    @classmethod
    def _unregister_lookup(cls, lookup, lookup_name=None):
        """
        Remove given lookup from cls lookups. For use in tests only as it's
        not thread-safe.
        """
        if lookup_name is None:
            lookup_name = lookup.lookup_name
        del cls.class_lookups[lookup_name]


def select_related_descend(field, restricted, requested, load_fields, reverse=False):
    """
    Return True if this field should be used to descend deeper for
    select_related() purposes. Used by both the query construction code
    (sql.query.fill_related_selections()) and the model instance creation code
    (query.get_klass_info()).

    Arguments:
     * field - the field to be checked
     * restricted - a boolean field, indicating if the field list has been
       manually restricted using a requested clause)
     * requested - The select_related() dictionary.
     * load_fields - the set of fields to be loaded on this model
     * reverse - boolean, True if we are checking a reverse select related
    """
    if not field.remote_field:
        return False
    if field.remote_field.parent_link and not reverse:
        return False
    if restricted:
        if reverse and field.related_query_name() not in requested:
            return False
        if not reverse and field.name not in requested:
            return False
    if not restricted and field.null:
        return False
    if load_fields:
        if field.attname not in load_fields:
            if restricted and field.name in requested:
                msg = (
                    'Field %s.%s cannot be both deferred and traversed using '
                    'select_related at the same time.'
                ) % (field.model._meta.object_name, field.name)
                raise FieldError(msg)
    return True


def refs_expression(lookup_parts, annotations):
    """
    Check if the lookup_parts contains references to the given annotations set.
    Because the LOOKUP_SEP is contained in the default annotation names, check
    each prefix of the lookup_parts for a match.
    """
    for n in range(1, len(lookup_parts) + 1):
        level_n_lookup = LOOKUP_SEP.join(lookup_parts[0:n])
        if level_n_lookup in annotations and annotations[level_n_lookup]:
            return annotations[level_n_lookup], lookup_parts[n:]
    return False, ()


def check_rel_lookup_compatibility(model, target_opts, field):
    """
    Check that self.model is compatible with target_opts. Compatibility
    is OK if:
      1) model and opts match (where proxy inheritance is removed)
      2) model is parent of opts' model or the other way around
    """
    def check(opts):
        return (
            model._meta.concrete_model == opts.concrete_model or
            opts.concrete_model in model._meta.get_parent_list() or
            model in opts.get_parent_list()
        )
    # If the field is a primary key, then doing a query against the field's
    # model is ok, too. Consider the case:
    # class Restaurant(models.Model):
    #     place = OneToOneField(Place, primary_key=True):
    # Restaurant.objects.filter(pk__in=Restaurant.objects.all()).
    # If we didn't have the primary key check, then pk__in (== place__in) would
    # give Place's opts as the target opts, but Restaurant isn't compatible
    # with that. This logic applies only to primary keys, as when doing __in=qs,
    # we are going to turn this into __in=qs.values('pk') later on.
    return (
        check(target_opts) or
        (getattr(field, 'primary_key', False) and check(field.model._meta))
    )


class FilteredRelation:
    """Specify custom filtering in the ON clause of SQL joins."""

    def __init__(self, relation_name, *, condition=Q()):
        if not relation_name:
            raise ValueError('relation_name cannot be empty.')
        self.relation_name = relation_name
        self.alias = None
        if not isinstance(condition, Q):
            raise ValueError('condition argument must be a Q() instance.')
        self.condition = condition
        self.path = []

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.relation_name == other.relation_name and
            self.alias == other.alias and
            self.condition == other.condition
        )

    def clone(self):
        clone = FilteredRelation(self.relation_name, condition=self.condition)
        clone.alias = self.alias
        clone.path = self.path[:]
        return clone

    def resolve_expression(self, *args, **kwargs):
        """
        QuerySet.annotate() only accepts expression-like arguments
        (with a resolve_expression() method).
        """
        raise NotImplementedError('FilteredRelation.resolve_expression() is unused.')

    def as_sql(self, compiler, connection):
        # Resolve the condition in Join.filtered_relation.
        query = compiler.query
        where = query.build_filtered_relation_q(self.condition, reuse=set(self.path))
        return compiler.compile(where)
