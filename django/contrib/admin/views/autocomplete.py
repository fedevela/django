from django.apps import apps
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.http import Http404, JsonResponse
from django.views.generic.list import BaseListView


class AutocompleteJsonView(BaseListView):
    """Handle AutocompleteWidget's AJAX requests for data."""
    paginate_by = 20
    admin_site = None

    def serialize_result(self, obj, to_field_name):
        """Convert the provided model object to a dictionary."""
        return {'id': str(getattr(obj, to_field_name)), 'text': str(obj)}

    # Successful-response boundary (GUID: ACJ-006, ACJ-007): get() alone owns
    # the top-level results/pagination envelope. Per-result mappings enter that
    # boundary through serialize_result(), while next-page state enters through
    # BaseListView's page_obj; neither dependency owns or may replace the
    # response shape or the pagination.more integration contract.

    def get(self, request, *args, **kwargs):
        """
        Return a JsonResponse with search results of the form:
        {
            results: [{id: "123" text: "foo"}],
            pagination: {more: true}
        }
        """
        self.term, self.model_admin, self.source_field, to_field_name = self.process_request(request)

        # Authentication and authorization preservation pseudocode (GUID: ACJ-008):
        # Ask the resolved related-model admin to evaluate its existing view
        # permission for the request; do not involve result serialization in
        # this decision.
        # If the request is unauthenticated and that existing permission check
        # rejects it, transition to the existing PermissionDenied failure path.
        # If the request is authenticated but lacks the required related-model
        # permission, transition to the same PermissionDenied failure path.
        # If the existing permission check allows the request, transition to
        # queryset evaluation and only then to result serialization.
        # If permission evaluation itself fails, propagate that failure without
        # querying or serializing results and without replacing its response.
        if not self.has_perm(request):
            raise PermissionDenied

        self.object_list = self.get_queryset()
        context = self.get_context_data()
        # Successful response envelope pseudocode (GUID: ACJ-006, ACJ-007):
        # Receive the serialized current-page results and current page object.
        # Construct one top-level mapping containing both `results` and
        # `pagination`; routing entries through serialize_result must not
        # remove, rename, or replace either member.
        # If the current page has a next page, set pagination.more to true.
        # Otherwise, set pagination.more to false.
        # Return the mapping as the successful JSON response. If page-state
        # inspection or result serialization fails, propagate that failure;
        # do not emit a partial or altered successful-response envelope.
        return JsonResponse({
            'results': [
                self.serialize_result(obj, to_field_name)
                for obj in context['object_list']
            ],
            'pagination': {'more': context['page_obj'].has_next()},
        })

    def get_paginator(self, *args, **kwargs):
        """Use the ModelAdmin's paginator."""
        return self.model_admin.get_paginator(self.request, *args, **kwargs)

    def get_queryset(self):
        """Return queryset based on ModelAdmin.get_search_results()."""
        qs = self.model_admin.get_queryset(self.request)
        qs = qs.complex_filter(self.source_field.get_limit_choices_to())
        qs, search_use_distinct = self.model_admin.get_search_results(self.request, qs, self.term)
        if search_use_distinct:
            qs = qs.distinct()
        return qs

    # Target-field resolution boundary (GUID: ACJ-009): process_request() owns
    # source-field lookup, relation traversal, target-field normalization, and
    # the related ModelAdmin policy check. Model metadata is its resolution
    # dependency and ModelAdmin.to_field_allowed() is its policy authority.
    # get() may consume only the validated source_field and to_field_name
    # returned across this seam; querying and serialize_result() remain
    # downstream and must not re-resolve, broaden, or translate that decision.

    def process_request(self, request):
        """
        Validate request integrity, extract and return request parameters.

        Since the subsequent view permission check requires the target model
        admin, which is determined here, raise PermissionDenied if the
        requested app, model or field are malformed.

        Raise Http404 if the target model admin is not configured properly with
        search_fields.
        """
        term = request.GET.get('term', '')
        try:
            app_label = request.GET['app_label']
            model_name = request.GET['model_name']
            field_name = request.GET['field_name']
        except KeyError as e:
            raise PermissionDenied from e

        # Retrieve objects from parameters.
        try:
            source_model = apps.get_model(app_label, model_name)
        except LookupError as e:
            raise PermissionDenied from e

        # Target-field validation preservation pseudocode (GUID: ACJ-009):
        # Resolve field_name from the source model before any result is
        # serialized; if no such field exists, propagate the existing
        # PermissionDenied rejection and stop processing.
        # From the resolved source field, resolve its related model; if the
        # field has no usable relation, propagate the existing PermissionDenied
        # rejection and stop processing.
        # Resolve the relation's configured target field, falling back to the
        # related model primary-key field exactly as before, and normalize that
        # resolved field to its attribute name.
        # Ask the related ModelAdmin whether that normalized target attribute is
        # allowed. If it is not allowed, propagate the existing PermissionDenied
        # rejection; do not query or serialize results.
        # Otherwise, return the unchanged resolved source field and normalized
        # target attribute to the caller so later serialization uses the same
        # identifier. Propagate resolution failures without introducing a new
        # permitted field, fallback, or error translation.
        try:
            source_field = source_model._meta.get_field(field_name)
        except FieldDoesNotExist as e:
            raise PermissionDenied from e
        try:
            remote_model = source_field.remote_field.model
        except AttributeError as e:
            raise PermissionDenied from e
        try:
            model_admin = self.admin_site._registry[remote_model]
        except KeyError as e:
            raise PermissionDenied from e

        # Validate suitability of objects.
        if not model_admin.get_search_fields(request):
            raise Http404(
                '%s must have search_fields for the autocomplete_view.' %
                type(model_admin).__qualname__
            )

        to_field_name = getattr(source_field.remote_field, 'field_name', remote_model._meta.pk.attname)
        to_field_name = remote_model._meta.get_field(to_field_name).attname
        if not model_admin.to_field_allowed(request, to_field_name):
            raise PermissionDenied

        return term, model_admin, source_field, to_field_name

    # Authorization adapter boundary (GUID: ACJ-008): AutocompleteJsonView
    # owns permission-check sequencing, while the resolved related ModelAdmin
    # remains the sole permission authority through has_view_permission().
    # Queryset and serialization dependencies stay downstream of this adapter
    # and must not participate in, bypass, or translate its decision.

    def has_perm(self, request, obj=None):
        """Check if user has permission to access the related model."""
        return self.model_admin.has_view_permission(request, obj=obj)
