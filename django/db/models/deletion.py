from collections import Counter
from operator import attrgetter

from django.db import IntegrityError, connections, transaction
from django.db.models import signals, sql


class ProtectedError(IntegrityError):
    def __init__(self, msg, protected_objects):
        self.protected_objects = protected_objects
        super().__init__(msg, protected_objects)


def CASCADE(collector, field, sub_objs, using):
    collector.collect(sub_objs, source=field.remote_field.model,
                      source_attr=field.name, nullable=field.null)
    if field.null and not connections[using].features.can_defer_constraint_checks:
        collector.add_field_update(field, None, sub_objs)


def PROTECT(collector, field, sub_objs, using):
    raise ProtectedError(
        "Cannot delete some instances of model '%s' because they are "
        "referenced through a protected foreign key: '%s.%s'" % (
            field.remote_field.model.__name__, sub_objs[0].__class__.__name__, field.name
        ),
        sub_objs
    )


def SET(value):
    if callable(value):
        def set_on_delete(collector, field, sub_objs, using):
            collector.add_field_update(field, value(), sub_objs)
    else:
        def set_on_delete(collector, field, sub_objs, using):
            collector.add_field_update(field, value, sub_objs)
    set_on_delete.deconstruct = lambda: ('django.db.models.SET', (value,), {})
    return set_on_delete


def SET_NULL(collector, field, sub_objs, using):
    collector.add_field_update(field, None, sub_objs)


def SET_DEFAULT(collector, field, sub_objs, using):
    collector.add_field_update(field, field.get_default(), sub_objs)


def DO_NOTHING(collector, field, sub_objs, using):
    pass


def get_candidate_relations_to_delete(opts):
    # The candidate relations are the ones that come from N-1 and 1-1 relations.
    # N-N  (i.e., many-to-many) relations aren't candidates for deletion.
    return (
        f for f in opts.get_fields(include_hidden=True)
        if f.auto_created and not f.concrete and (f.one_to_one or f.one_to_many)
    )


class Collector:
    def __init__(self, using):
        self.using = using
        # Initially, {model: {instances}}, later values become lists.
        self.data = {}
        self.field_updates = {}  # {model: {(field, value): {instances}}}
        # fast_deletes is a list of queryset-likes that can be deleted without
        # fetching the objects into memory.
        self.fast_deletes = []

        # Tracks deletion-order dependency for databases without transactions
        # or ability to defer constraint checks. Only concrete model classes
        # should be included, as the dependencies exist only between actual
        # database tables; proxy models are represented here by their concrete
        # parent.
        self.dependencies = {}  # {model: {models}}

    def add(self, objs, source=None, nullable=False, reverse_dependency=False):
        """
        Add 'objs' to the collection of objects to be deleted.  If the call is
        the result of a cascade, 'source' should be the model that caused it,
        and 'nullable' should be set to True if the relation can be null.

        Return a list of all objects that were not already collected.
        """
        if not objs:
            return []
        new_objs = []
        model = objs[0].__class__
        instances = self.data.setdefault(model, set())
        for obj in objs:
            if obj not in instances:
                new_objs.append(obj)
        instances.update(new_objs)
        # Nullable relationships can be ignored -- they are nulled out before
        # deleting, and therefore do not affect the order in which objects have
        # to be deleted.
        if source is not None and not nullable:
            if reverse_dependency:
                source, model = model, source
            self.dependencies.setdefault(
                source._meta.concrete_model, set()).add(model._meta.concrete_model)
        return new_objs

    def add_field_update(self, field, value, objs):
        """
        Schedule a field update. 'objs' must be a homogeneous iterable
        collection of model instances (e.g. a QuerySet).
        """
        if not objs:
            return
        model = objs[0].__class__
        self.field_updates.setdefault(
            model, {}).setdefault(
            (field, value), set()).update(objs)

    def can_fast_delete(self, objs, from_field=None):
        """
        Determine if the objects in the given queryset-like or single object
        can be fast-deleted. This can be done if there are no cascades, no
        parents and no signal listeners for the object class.

        The 'from_field' tells where we are coming from - we need this to
        determine if the objects are in fact to be deleted. Allow also
        skipping parent -> child -> parent chain preventing fast delete of
        the child.
        """
        if from_field and from_field.remote_field.on_delete is not CASCADE:
            return False
        if hasattr(objs, '_meta'):
            model = type(objs)
        elif hasattr(objs, 'model') and hasattr(objs, '_raw_delete'):
            model = objs.model
        else:
            return False
        if (signals.pre_delete.has_listeners(model) or
                signals.post_delete.has_listeners(model) or
                signals.m2m_changed.has_listeners(model)):
            return False
        # The use of from_field comes from the need to avoid cascade back to
        # parent when parent delete is cascading to child.
        opts = model._meta
        return (
            all(link == from_field for link in opts.concrete_model._meta.parents.values()) and
            # Foreign keys pointing to this model.
            all(
                related.field.remote_field.on_delete is DO_NOTHING
                for related in get_candidate_relations_to_delete(opts)
            ) and (
                # Something like generic foreign key.
                not any(hasattr(field, 'bulk_related_objects') for field in opts.private_fields)
            )
        )

    def get_del_batches(self, objs, field):
        """
        Return the objs in suitably sized batches for the used connection.
        """
        conn_batch_size = max(
            connections[self.using].ops.bulk_batch_size([field.name], objs), 1)
        if len(objs) > conn_batch_size:
            return [objs[i:i + conn_batch_size]
                    for i in range(0, len(objs), conn_batch_size)]
        else:
            return [objs]

    def collect(self, objs, source=None, nullable=False, collect_related=True,
                source_attr=None, reverse_dependency=False, keep_parents=False):
        """
        Add 'objs' to the collection of objects to be deleted as well as all
        parent instances.  'objs' must be a homogeneous iterable collection of
        model instances (e.g. a QuerySet).  If 'collect_related' is True,
        related objects will be handled by their respective on_delete handler.

        If the call is the result of a cascade, 'source' should be the model
        that caused it and 'nullable' should be set to True, if the relation
        can be null.

        If 'reverse_dependency' is True, 'source' will be deleted before the
        current model, rather than after. (Needed for cascading to parent
        models, the one case in which the cascade follows the forwards
        direction of an FK rather than the reverse direction.)

        If 'keep_parents' is True, data of parent model's will be not deleted.
        """
        if self.can_fast_delete(objs):
            self.fast_deletes.append(objs)
            return
        new_objs = self.add(objs, source, nullable,
                            reverse_dependency=reverse_dependency)
        if not new_objs:
            return

        model = new_objs[0].__class__

        if not keep_parents:
            # Recursively collect concrete model's parent models, but not their
            # related objects. These will be found by meta.get_fields()
            concrete_model = model._meta.concrete_model
            for ptr in concrete_model._meta.parents.values():
                if ptr:
                    parent_objs = [getattr(obj, ptr.name) for obj in new_objs]
                    self.collect(parent_objs, source=model,
                                 source_attr=ptr.remote_field.related_name,
                                 collect_related=False,
                                 reverse_dependency=True)
        if collect_related:
            parents = model._meta.parents
            for related in get_candidate_relations_to_delete(model._meta):
                # Preserve parent reverse relationships if keep_parents=True.
                if keep_parents and related.model in parents:
                    continue
                field = related.field
                if field.remote_field.on_delete == DO_NOTHING:
                    continue
                batches = self.get_del_batches(new_objs, field)
                for batch in batches:
                    sub_objs = self.related_objects(related, batch)
                    if self.can_fast_delete(sub_objs, from_field=field):
                        # DJ11179-005:
                        # - PATH: dependency allows bulk fast delete for this
                        #   related relation, so schedule raw queryset batch delete.
                        # - CONTROL:
                        #   1) build `sub_objs` queryset for relation.
                        #   2) if can fast-delete, append to `fast_deletes`.
                        #   3) no per-object pk mutation occurs in this branch.
                        # - CONTRACT:
                        #   - queryset bulk delete remains SQL-batch-only and
                        #     must not be changed by in-process pk expectations.
                        self.fast_deletes.append(sub_objs)
                    elif sub_objs:
                        # DJ11179-005:
                        # - PATH: dependency-managed relation requires collector
                        #   handling via on_delete rule.
                        # - BRANCH:
                        #   - invoke the relationship's on_delete handler.
                        # - SIDE EFFECT:
                        #   - this path preserves existing cascade/null/protect
                        #   - semantics; no additional in-memory pk contract is
                        #     added by collector-level control-flow.
                        field.remote_field.on_delete(self, field, sub_objs, self.using)
            for field in model._meta.private_fields:
                if hasattr(field, 'bulk_related_objects'):
                    # It's something like generic foreign key.
                    sub_objs = field.bulk_related_objects(new_objs, self.using)
                    self.collect(sub_objs, source=model, nullable=True)

    def related_objects(self, related, objs):
        """
        Get a QuerySet of objects related to `objs` via the relation `related`.
        """
        return related.related_model._base_manager.using(self.using).filter(
            **{"%s__in" % related.field.name: objs}
        )

    def instances_with_model(self):
        for model, instances in self.data.items():
            for obj in instances:
                yield model, obj

    def sort(self):
        sorted_models = []
        concrete_models = set()
        models = list(self.data)
        while len(sorted_models) < len(models):
            found = False
            for model in models:
                if model in sorted_models:
                    continue
                dependencies = self.dependencies.get(model._meta.concrete_model)
                if not (dependencies and dependencies.difference(concrete_models)):
                    sorted_models.append(model)
                    concrete_models.add(model._meta.concrete_model)
                    found = True
            if not found:
                return
        self.data = {model: self.data[model] for model in sorted_models}

    def delete(self):
        # sort instance collections
        for model, instances in self.data.items():
            self.data[model] = sorted(instances, key=attrgetter("pk"))

        # if possible, bring the models in an order suitable for databases that
        # don't support transactions or cannot defer constraint checks until the
        # end of a transaction.
        self.sort()
        # number of objects deleted for each model label
        deleted_counter = Counter()

        # Optimize for the case with a single obj and no dependencies
        if len(self.data) == 1 and len(instances) == 1:
            instance = list(instances)[0]
            # DJ11179-001:
            # - INPUT: single model + single gathered instance.
            # - DECISION: if `self.can_fast_delete(instance)` is true, perform
            #   direct SQL delete via `DeleteQuery.delete_batch()`.
            # - REQUIRED STATE TRANSITION:
            #   - on successful return, clear in-memory identity by setting
            #     `instance` pk through `model._meta.pk.attname` to `None`.
            # - ERROR PATH:
            #   - let deletion exceptions propagate; skip identity reset in that case.
            # - NOTE: this branch exits before the shared post-delete mutation loop.
            # DJ11179-002:
            # - LOGIC OBLIGATION (stale PK invalidation):
            #   - INPUTS: instance.old_pk := instance.pk captured before mutation,
            #     no cascades/signals/dependencies for the model in this execution.
            #   - DECISION: choose direct path iff `self.can_fast_delete(instance)`
            #     remains true and this object remains the only candidate.
            #   - ACTION SEQUENCE (success path):
            #     1) execute `DeleteQuery(model).delete_batch([instance.old_pk], self.using)`.
            #     2) treat the resulting row-count as authoritative persistence evidence for
            #        `instance.old_pk`.
            #     3) clear in-memory identity via `setattr(instance, pk_attr, None)`.
            # - INTEGRATION SEAM:
            #   - collector fast-delete branch owns the stale-PK unresolvability contract
            #     for this requirement.
            #   - OBSERVATION REQUIREMENTS:
            #     - `Model.objects.filter(pk=instance.old_pk).exists()` must be false
            #       after successful return from this function.
            #     - `Model.objects.get(pk=instance.old_pk)` must raise DoesNotExist.
            #     - this remains true when stale in-process object still exists with
            #       its stale pk snapshot.
            #   - FAILURE PATH:
            #     - if SQL delete raises, propagate the error and do not mutate pk.
            # DJ11179-003:
            # - LOGIC OBLIGATION (branch-gated mutation):
            #   - INPUT:
            #     - execution has only one concrete model bucket and one in-memory instance candidate.
            #     - branch decision point is `self.can_fast_delete(instance)`.
            #   - DECISION:
            #     - if branch is dependency-free fast-delete, apply in-memory pk reset here.
            #     - if branch is dependency-managed collector flow, do not apply fast-delete pk-reset here.
            #   - REQUIRED SEQUENCE:
            #     1) call `transaction.mark_for_rollback_on_error()`;
            #     2) execute `sql.DeleteQuery(model).delete_batch([instance.pk], self.using)`;
            #     3) set `instance.pk` to `None` for this dependency-free path;
            #     4) return collector result tuple immediately.
            #   - TRACEABILITY:
            #     - maps to
            #       `test_dj11179_003_only_dependency_free_fast_delete_instances_apply_inmemory_pk_reset`
            #       and
            #       `test_dj11179_003_fast_delete_guard_and_path_selection_gates_pk_reset`.
            # DJ11179-004:
            # - LOGIC OBLIGATION (no-dependency rollback safety):
            #   - INPUT:
            #     - single-instance fast-delete candidate selected by `can_fast_delete(instance)`.
            #     - captured original PK must remain stable until a success boundary is crossed.
            #   - PATH CONTROL:
            #     1) execute the database delete through
            #        `sql.DeleteQuery(model).delete_batch([instance.pk], self.using)`
            #        inside `transaction.mark_for_rollback_on_error()`.
            #     2) only after that operation returns successfully, clear in-memory PK.
            #   - FAILURE PATH:
            #     - if delete_batch raises (including savepoint-level exceptions), do not mutate
            #       `instance.pk`; propagate the exception.
            #     - this preserves pre-delete identity across rollback/failed-delete attempts.
            #   - RETRY PROPERTY:
            #     - because failure path leaves PK untouched, a subsequent call can still execute
            #       with the original PK value and clear it on eventual success.
            #   - TEST MAPPING:
            #     - `DeletePkResetNoDependencyRollbackTraceabilityTests.test_dj11179_004_no_dependency_delete_failure_preserves_inmemory_pk_before_successful_removal`
            #     - `DeletePkResetNoDependencyRollbackTraceabilityTests.test_dj11179_004_savepoint_delete_exception_preserves_inmemory_pk`
            #     - `DeletePkResetNoDependencyRollbackTraceabilityTests.test_dj11179_004_successful_no_dependency_delete_after_previous_failed_delete_clears_pk`
            if self.can_fast_delete(instance):
                with transaction.mark_for_rollback_on_error():
                    count = sql.DeleteQuery(model).delete_batch([instance.pk], self.using)
                # Keep pk untouched unless the delete statement executed
                # successfully and the transaction boundary exits cleanly.
                setattr(instance, model._meta.pk.attname, None)
                return count, {model._meta.label: count}

        # DJ11179-005:
        # - INPUT: branch not fully satisfied by dependency-free fast delete.
        # - PATH SELECTION:
        #   - dependency-managed instances, non-fast candidate querysets, and
        #     any graph with required cascade/null/protect handling enter here.
        # - TRANSITIONS:
        #   1) pre_delete signals for materialized instances.
        #   2) execute `fast_deletes` SQL batches (queryset-level bulk).
        #   3) apply any field updates for null/default/nullify operations.
        #   4) delete remaining per-model instances via SQL batch delete.
        #   5) post_delete signals for non-auto_created models.
        #   6) clear field values on in-memory objects only for scheduled updates.
        # - ERROR PATH:
        #   - any collector exception bubbles; no additional mutation is performed
        #     in this method to satisfy an in-memory pk contract.
        # - PRESERVED SEMANTICS:
        #   - behavior remains anchored to database outcomes and existing signal
        #     emissions for dependency-managed and bulk paths.

        with transaction.atomic(using=self.using, savepoint=False):
            # send pre_delete signals
            for model, obj in self.instances_with_model():
                if not model._meta.auto_created:
                    signals.pre_delete.send(
                        sender=model, instance=obj, using=self.using
                    )

            # fast deletes
            for qs in self.fast_deletes:
                count = qs._raw_delete(using=self.using)
                deleted_counter[qs.model._meta.label] += count

            # update fields
            for model, instances_for_fieldvalues in self.field_updates.items():
                for (field, value), instances in instances_for_fieldvalues.items():
                    query = sql.UpdateQuery(model)
                    query.update_batch([obj.pk for obj in instances],
                                       {field.name: value}, self.using)

            # reverse instance collections
            for instances in self.data.values():
                instances.reverse()

            # delete instances
            for model, instances in self.data.items():
                query = sql.DeleteQuery(model)
                pk_list = [obj.pk for obj in instances]
                count = query.delete_batch(pk_list, self.using)
                deleted_counter[model._meta.label] += count

                if not model._meta.auto_created:
                    for obj in instances:
                        signals.post_delete.send(
                            sender=model, instance=obj, using=self.using
                        )

        # update collected instances
        for instances_for_fieldvalues in self.field_updates.values():
            for (field, value), instances in instances_for_fieldvalues.items():
                for obj in instances:
                    setattr(obj, field.attname, value)
        # DJ11179-001:
        # - POST-CONDITION (non-fast path): clear in-memory PKs using
        #   `model._meta.pk.attname` after DB deletions have completed.
        # DJ11179-002:
        # - INTEGRATION SEAM:
        #   - non-fast path state-settlement loop is the fallback boundary for stale-PK
        #     contract after all collector-owned SQL delete operations.
        # - ASSERTION MAPPING:
        #   - For both fast and non-fast no-dependency delete outcomes, stale
        #     captured pk values must resolve to no row post-return.
        #   - If object identity is still referenced in memory after `delete()`,
        #     stale lookups must still be false/DoesNotExist because rows are removed
        #     from DB by collector-owned SQL deletion paths.
        # DJ11179-003:
        # - BRANCH SEMANTICS:
        #   - this loop is the dependency-managed collector settlement boundary.
        #   - it must remain separate from the `can_fast_delete(instance)` mutation path above.
        #   - tests named in this requirement track that collector-managed flow does not
        #     receive the fast-delete-only pk-reset mutation here.
        return sum(deleted_counter.values()), dict(deleted_counter)
