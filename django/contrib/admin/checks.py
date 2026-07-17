import collections
from itertools import chain

from django.apps import apps
from django.conf import settings
from django.contrib.admin.utils import (
    NotRelationField,
    flatten,
    get_fields_from_path,
    label_for_field,
)
from django.core import checks
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.db.models.expressions import Combinable
from django.forms.models import BaseModelForm, BaseModelFormSet, _get_foreign_key
from django.template import engines
from django.template.backends.django import DjangoTemplates
from django.utils.module_loading import import_string


def _issubclass(cls, classinfo):
    """
    issubclass() variant that doesn't raise an exception if cls isn't a
    class.
    """
    try:
        return issubclass(cls, classinfo)
    except TypeError:
        return False


def _contains_subclass(class_path, candidate_paths):
    """
    Return whether or not a dotted class path (or a subclass of that class) is
    found in a list of candidate paths.
    """
    cls = import_string(class_path)
    for path in candidate_paths:
        try:
            candidate_cls = import_string(path)
        except ImportError:
            # ImportErrors are raised elsewhere.
            continue
        if _issubclass(candidate_cls, cls):
            return True
    return False


def check_admin_app(app_configs, **kwargs):
    from django.contrib.admin.sites import all_sites

    errors = []
    for site in all_sites:
        errors.extend(site.check(app_configs))
    return errors


def check_dependencies(**kwargs):
    """
    Check that the admin's dependencies are correctly installed.
    """
    from django.contrib.admin.sites import all_sites

    if not apps.is_installed("django.contrib.admin"):
        return []
    errors = []
    app_dependencies = (
        ("django.contrib.contenttypes", 401),
        ("django.contrib.auth", 405),
        ("django.contrib.messages", 406),
    )
    for app_name, error_code in app_dependencies:
        if not apps.is_installed(app_name):
            errors.append(
                checks.Error(
                    "'%s' must be in INSTALLED_APPS in order to use the admin "
                    "application." % app_name,
                    id="admin.E%d" % error_code,
                )
            )
    for engine in engines.all():
        if isinstance(engine, DjangoTemplates):
            django_templates_instance = engine.engine
            break
    else:
        django_templates_instance = None
    if not django_templates_instance:
        errors.append(
            checks.Error(
                "A 'django.template.backends.django.DjangoTemplates' instance "
                "must be configured in TEMPLATES in order to use the admin "
                "application.",
                id="admin.E403",
            )
        )
    else:
        if (
            "django.contrib.auth.context_processors.auth"
            not in django_templates_instance.context_processors
            and _contains_subclass(
                "django.contrib.auth.backends.ModelBackend",
                settings.AUTHENTICATION_BACKENDS,
            )
        ):
            errors.append(
                checks.Error(
                    "'django.contrib.auth.context_processors.auth' must be "
                    "enabled in DjangoTemplates (TEMPLATES) if using the default "
                    "auth backend in order to use the admin application.",
                    id="admin.E402",
                )
            )
        if (
            "django.contrib.messages.context_processors.messages"
            not in django_templates_instance.context_processors
        ):
            errors.append(
                checks.Error(
                    "'django.contrib.messages.context_processors.messages' must "
                    "be enabled in DjangoTemplates (TEMPLATES) in order to use "
                    "the admin application.",
                    id="admin.E404",
                )
            )
        sidebar_enabled = any(site.enable_nav_sidebar for site in all_sites)
        if (
            sidebar_enabled
            and "django.template.context_processors.request"
            not in django_templates_instance.context_processors
        ):
            errors.append(
                checks.Warning(
                    "'django.template.context_processors.request' must be enabled "
                    "in DjangoTemplates (TEMPLATES) in order to use the admin "
                    "navigation sidebar.",
                    id="admin.W411",
                )
            )

    if not _contains_subclass(
        "django.contrib.auth.middleware.AuthenticationMiddleware", settings.MIDDLEWARE
    ):
        errors.append(
            checks.Error(
                "'django.contrib.auth.middleware.AuthenticationMiddleware' must "
                "be in MIDDLEWARE in order to use the admin application.",
                id="admin.E408",
            )
        )
    if not _contains_subclass(
        "django.contrib.messages.middleware.MessageMiddleware", settings.MIDDLEWARE
    ):
        errors.append(
            checks.Error(
                "'django.contrib.messages.middleware.MessageMiddleware' must "
                "be in MIDDLEWARE in order to use the admin application.",
                id="admin.E409",
            )
        )
    if not _contains_subclass(
        "django.contrib.sessions.middleware.SessionMiddleware", settings.MIDDLEWARE
    ):
        errors.append(
            checks.Error(
                "'django.contrib.sessions.middleware.SessionMiddleware' must "
                "be in MIDDLEWARE in order to use the admin application.",
                hint=(
                    "Insert "
                    "'django.contrib.sessions.middleware.SessionMiddleware' "
                    "before "
                    "'django.contrib.auth.middleware.AuthenticationMiddleware'."
                ),
                id="admin.E410",
            )
        )
    return errors


class BaseModelAdminChecks:
    def check(self, admin_obj, **kwargs):
        return [
            *self._check_autocomplete_fields(admin_obj),
            *self._check_raw_id_fields(admin_obj),
            *self._check_fields(admin_obj),
            *self._check_fieldsets(admin_obj),
            *self._check_exclude(admin_obj),
            *self._check_form(admin_obj),
            *self._check_filter_vertical(admin_obj),
            *self._check_filter_horizontal(admin_obj),
            *self._check_radio_fields(admin_obj),
            *self._check_prepopulated_fields(admin_obj),
            *self._check_view_on_site_url(admin_obj),
            *self._check_ordering(admin_obj),
            *self._check_readonly_fields(admin_obj),
        ]

    def _check_autocomplete_fields(self, obj):
        """
        Check that `autocomplete_fields` is a list or tuple of model fields.
        """
        if not isinstance(obj.autocomplete_fields, (list, tuple)):
            return must_be(
                "a list or tuple",
                option="autocomplete_fields",
                obj=obj,
                id="admin.E036",
            )
        else:
            return list(
                chain.from_iterable(
                    [
                        self._check_autocomplete_fields_item(
                            obj, field_name, "autocomplete_fields[%d]" % index
                        )
                        for index, field_name in enumerate(obj.autocomplete_fields)
                    ]
                )
            )

    def _check_autocomplete_fields_item(self, obj, field_name, label):
        """
        Check that an item in `autocomplete_fields` is a ForeignKey or a
        ManyToManyField and that the item has a related ModelAdmin with
        search_fields defined.
        """
        try:
            field = obj.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return refer_to_missing_field(
                field=field_name, option=label, obj=obj, id="admin.E037"
            )
        else:
            if not field.many_to_many and not isinstance(field, models.ForeignKey):
                return must_be(
                    "a foreign key or a many-to-many field",
                    option=label,
                    obj=obj,
                    id="admin.E038",
                )
            related_admin = obj.admin_site._registry.get(field.remote_field.model)
            if related_admin is None:
                return [
                    checks.Error(
                        'An admin for model "%s" has to be registered '
                        "to be referenced by %s.autocomplete_fields."
                        % (
                            field.remote_field.model.__name__,
                            type(obj).__name__,
                        ),
                        obj=obj.__class__,
                        id="admin.E039",
                    )
                ]
            elif not related_admin.search_fields:
                return [
                    checks.Error(
                        '%s must define "search_fields", because it\'s '
                        "referenced by %s.autocomplete_fields."
                        % (
                            related_admin.__class__.__name__,
                            type(obj).__name__,
                        ),
                        obj=obj.__class__,
                        id="admin.E040",
                    )
                ]
            return []

    def _check_raw_id_fields(self, obj):
        """Check that `raw_id_fields` only contains field names that are listed
        on the model."""

        if not isinstance(obj.raw_id_fields, (list, tuple)):
            return must_be(
                "a list or tuple", option="raw_id_fields", obj=obj, id="admin.E001"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_raw_id_fields_item(
                        obj, field_name, "raw_id_fields[%d]" % index
                    )
                    for index, field_name in enumerate(obj.raw_id_fields)
                )
            )

    def _check_raw_id_fields_item(self, obj, field_name, label):
        """Check an item of `raw_id_fields`, i.e. check that field named
        `field_name` exists in model `model` and is a ForeignKey or a
        ManyToManyField."""

        try:
            field = obj.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return refer_to_missing_field(
                field=field_name, option=label, obj=obj, id="admin.E002"
            )
        else:
            # Using attname is not supported.
            if field.name != field_name:
                return refer_to_missing_field(
                    field=field_name,
                    option=label,
                    obj=obj,
                    id="admin.E002",
                )
            if not field.many_to_many and not isinstance(field, models.ForeignKey):
                return must_be(
                    "a foreign key or a many-to-many field",
                    option=label,
                    obj=obj,
                    id="admin.E003",
                )
            else:
                return []

    def _check_fields(self, obj):
        """Check that `fields` only refer to existing fields, doesn't contain
        duplicates. Check if at most one of `fields` and `fieldsets` is defined.
        """

        if obj.fields is None:
            return []
        elif not isinstance(obj.fields, (list, tuple)):
            return must_be("a list or tuple", option="fields", obj=obj, id="admin.E004")
        elif obj.fieldsets:
            return [
                checks.Error(
                    "Both 'fieldsets' and 'fields' are specified.",
                    obj=obj.__class__,
                    id="admin.E005",
                )
            ]
        fields = flatten(obj.fields)
        if len(fields) != len(set(fields)):
            return [
                checks.Error(
                    "The value of 'fields' contains duplicate field(s).",
                    obj=obj.__class__,
                    id="admin.E006",
                )
            ]

        return list(
            chain.from_iterable(
                self._check_field_spec(obj, field_name, "fields")
                for field_name in obj.fields
            )
        )

    def _check_fieldsets(self, obj):
        """Check that fieldsets is properly formatted and doesn't contain
        duplicates."""

        if obj.fieldsets is None:
            return []
        elif not isinstance(obj.fieldsets, (list, tuple)):
            return must_be(
                "a list or tuple", option="fieldsets", obj=obj, id="admin.E007"
            )
        else:
            seen_fields = []
            return list(
                chain.from_iterable(
                    self._check_fieldsets_item(
                        obj, fieldset, "fieldsets[%d]" % index, seen_fields
                    )
                    for index, fieldset in enumerate(obj.fieldsets)
                )
            )

    def _check_fieldsets_item(self, obj, fieldset, label, seen_fields):
        """Check an item of `fieldsets`, i.e. check that this is a pair of a
        set name and a dictionary containing "fields" key."""

        if not isinstance(fieldset, (list, tuple)):
            return must_be("a list or tuple", option=label, obj=obj, id="admin.E008")
        elif len(fieldset) != 2:
            return must_be("of length 2", option=label, obj=obj, id="admin.E009")
        elif not isinstance(fieldset[1], dict):
            return must_be(
                "a dictionary", option="%s[1]" % label, obj=obj, id="admin.E010"
            )
        elif "fields" not in fieldset[1]:
            return [
                checks.Error(
                    "The value of '%s[1]' must contain the key 'fields'." % label,
                    obj=obj.__class__,
                    id="admin.E011",
                )
            ]
        elif not isinstance(fieldset[1]["fields"], (list, tuple)):
            return must_be(
                "a list or tuple",
                option="%s[1]['fields']" % label,
                obj=obj,
                id="admin.E008",
            )

        seen_fields.extend(flatten(fieldset[1]["fields"]))
        if len(seen_fields) != len(set(seen_fields)):
            return [
                checks.Error(
                    "There are duplicate field(s) in '%s[1]'." % label,
                    obj=obj.__class__,
                    id="admin.E012",
                )
            ]
        return list(
            chain.from_iterable(
                self._check_field_spec(obj, fieldset_fields, '%s[1]["fields"]' % label)
                for fieldset_fields in fieldset[1]["fields"]
            )
        )

    def _check_field_spec(self, obj, fields, label):
        """`fields` should be an item of `fields` or an item of
        fieldset[1]['fields'] for any `fieldset` in `fieldsets`. It should be a
        field name or a tuple of field names."""

        if isinstance(fields, tuple):
            return list(
                chain.from_iterable(
                    self._check_field_spec_item(
                        obj, field_name, "%s[%d]" % (label, index)
                    )
                    for index, field_name in enumerate(fields)
                )
            )
        else:
            return self._check_field_spec_item(obj, fields, label)

    def _check_field_spec_item(self, obj, field_name, label):
        if field_name in obj.readonly_fields:
            # Stuff can be put in fields that isn't actually a model field if
            # it's in readonly_fields, readonly_fields will handle the
            # validation of such things.
            return []
        else:
            try:
                field = obj.model._meta.get_field(field_name)
            except FieldDoesNotExist:
                # If we can't find a field on the model that matches, it could
                # be an extra field on the form.
                return []
            else:
                if (
                    isinstance(field, models.ManyToManyField)
                    and not field.remote_field.through._meta.auto_created
                ):
                    return [
                        checks.Error(
                            "The value of '%s' cannot include the ManyToManyField "
                            "'%s', because that field manually specifies a "
                            "relationship model." % (label, field_name),
                            obj=obj.__class__,
                            id="admin.E013",
                        )
                    ]
                else:
                    return []

    def _check_exclude(self, obj):
        """Check that exclude is a sequence without duplicates."""

        if obj.exclude is None:  # default value is None
            return []
        elif not isinstance(obj.exclude, (list, tuple)):
            return must_be(
                "a list or tuple", option="exclude", obj=obj, id="admin.E014"
            )
        elif len(obj.exclude) > len(set(obj.exclude)):
            return [
                checks.Error(
                    "The value of 'exclude' contains duplicate field(s).",
                    obj=obj.__class__,
                    id="admin.E015",
                )
            ]
        else:
            return []

    def _check_form(self, obj):
        """Check that form subclasses BaseModelForm."""
        if not _issubclass(obj.form, BaseModelForm):
            return must_inherit_from(
                parent="BaseModelForm", option="form", obj=obj, id="admin.E016"
            )
        else:
            return []

    def _check_filter_vertical(self, obj):
        """Check that filter_vertical is a sequence of field names."""
        if not isinstance(obj.filter_vertical, (list, tuple)):
            return must_be(
                "a list or tuple", option="filter_vertical", obj=obj, id="admin.E017"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_filter_item(
                        obj, field_name, "filter_vertical[%d]" % index
                    )
                    for index, field_name in enumerate(obj.filter_vertical)
                )
            )

    def _check_filter_horizontal(self, obj):
        """Check that filter_horizontal is a sequence of field names."""
        if not isinstance(obj.filter_horizontal, (list, tuple)):
            return must_be(
                "a list or tuple", option="filter_horizontal", obj=obj, id="admin.E018"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_filter_item(
                        obj, field_name, "filter_horizontal[%d]" % index
                    )
                    for index, field_name in enumerate(obj.filter_horizontal)
                )
            )

    def _check_filter_item(self, obj, field_name, label):
        """Check one item of `filter_vertical` or `filter_horizontal`, i.e.
        check that given field exists and is a ManyToManyField."""

        try:
            field = obj.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return refer_to_missing_field(
                field=field_name, option=label, obj=obj, id="admin.E019"
            )
        else:
            if not field.many_to_many:
                return must_be(
                    "a many-to-many field", option=label, obj=obj, id="admin.E020"
                )
            else:
                return []

    def _check_radio_fields(self, obj):
        """Check that `radio_fields` is a dictionary."""
        if not isinstance(obj.radio_fields, dict):
            return must_be(
                "a dictionary", option="radio_fields", obj=obj, id="admin.E021"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_radio_fields_key(obj, field_name, "radio_fields")
                    + self._check_radio_fields_value(
                        obj, val, 'radio_fields["%s"]' % field_name
                    )
                    for field_name, val in obj.radio_fields.items()
                )
            )

    def _check_radio_fields_key(self, obj, field_name, label):
        """Check that a key of `radio_fields` dictionary is name of existing
        field and that the field is a ForeignKey or has `choices` defined."""

        try:
            field = obj.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return refer_to_missing_field(
                field=field_name, option=label, obj=obj, id="admin.E022"
            )
        else:
            if not (isinstance(field, models.ForeignKey) or field.choices):
                return [
                    checks.Error(
                        "The value of '%s' refers to '%s', which is not an "
                        "instance of ForeignKey, and does not have a 'choices' "
                        "definition." % (label, field_name),
                        obj=obj.__class__,
                        id="admin.E023",
                    )
                ]
            else:
                return []

    def _check_radio_fields_value(self, obj, val, label):
        """Check type of a value of `radio_fields` dictionary."""

        from django.contrib.admin.options import HORIZONTAL, VERTICAL

        if val not in (HORIZONTAL, VERTICAL):
            return [
                checks.Error(
                    "The value of '%s' must be either admin.HORIZONTAL or "
                    "admin.VERTICAL." % label,
                    obj=obj.__class__,
                    id="admin.E024",
                )
            ]
        else:
            return []

    def _check_view_on_site_url(self, obj):
        if not callable(obj.view_on_site) and not isinstance(obj.view_on_site, bool):
            return [
                checks.Error(
                    "The value of 'view_on_site' must be a callable or a boolean "
                    "value.",
                    obj=obj.__class__,
                    id="admin.E025",
                )
            ]
        else:
            return []

    def _check_prepopulated_fields(self, obj):
        """Check that `prepopulated_fields` is a dictionary containing allowed
        field types."""
        if not isinstance(obj.prepopulated_fields, dict):
            return must_be(
                "a dictionary", option="prepopulated_fields", obj=obj, id="admin.E026"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_prepopulated_fields_key(
                        obj, field_name, "prepopulated_fields"
                    )
                    + self._check_prepopulated_fields_value(
                        obj, val, 'prepopulated_fields["%s"]' % field_name
                    )
                    for field_name, val in obj.prepopulated_fields.items()
                )
            )

    def _check_prepopulated_fields_key(self, obj, field_name, label):
        """Check a key of `prepopulated_fields` dictionary, i.e. check that it
        is a name of existing field and the field is one of the allowed types.
        """

        try:
            field = obj.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return refer_to_missing_field(
                field=field_name, option=label, obj=obj, id="admin.E027"
            )
        else:
            if isinstance(
                field, (models.DateTimeField, models.ForeignKey, models.ManyToManyField)
            ):
                return [
                    checks.Error(
                        "The value of '%s' refers to '%s', which must not be a "
                        "DateTimeField, a ForeignKey, a OneToOneField, or a "
                        "ManyToManyField." % (label, field_name),
                        obj=obj.__class__,
                        id="admin.E028",
                    )
                ]
            else:
                return []

    def _check_prepopulated_fields_value(self, obj, val, label):
        """Check a value of `prepopulated_fields` dictionary, i.e. it's an
        iterable of existing fields."""

        if not isinstance(val, (list, tuple)):
            return must_be("a list or tuple", option=label, obj=obj, id="admin.E029")
        else:
            return list(
                chain.from_iterable(
                    self._check_prepopulated_fields_value_item(
                        obj, subfield_name, "%s[%r]" % (label, index)
                    )
                    for index, subfield_name in enumerate(val)
                )
            )

    def _check_prepopulated_fields_value_item(self, obj, field_name, label):
        """For `prepopulated_fields` equal to {"slug": ("title",)},
        `field_name` is "title"."""

        try:
            obj.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return refer_to_missing_field(
                field=field_name, option=label, obj=obj, id="admin.E030"
            )
        else:
            return []

    def _check_ordering(self, obj):
        """Check that ordering refers to existing fields or is random."""

        # ordering = None
        if obj.ordering is None:  # The default value is None
            return []
        elif not isinstance(obj.ordering, (list, tuple)):
            return must_be(
                "a list or tuple", option="ordering", obj=obj, id="admin.E031"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_ordering_item(obj, field_name, "ordering[%d]" % index)
                    for index, field_name in enumerate(obj.ordering)
                )
            )

    def _check_ordering_item(self, obj, field_name, label):
        """Check that `ordering` refers to existing fields."""
        if isinstance(field_name, (Combinable, models.OrderBy)):
            if not isinstance(field_name, models.OrderBy):
                field_name = field_name.asc()
            if isinstance(field_name.expression, models.F):
                field_name = field_name.expression.name
            else:
                return []
        if field_name == "?" and len(obj.ordering) != 1:
            return [
                checks.Error(
                    "The value of 'ordering' has the random ordering marker '?', "
                    "but contains other fields as well.",
                    hint='Either remove the "?", or remove the other fields.',
                    obj=obj.__class__,
                    id="admin.E032",
                )
            ]
        elif field_name == "?":
            return []
        elif LOOKUP_SEP in field_name:
            # Skip ordering in the format field1__field2 (FIXME: checking
            # this format would be nice, but it's a little fiddly).
            return []
        else:
            field_name = field_name.removeprefix("-")
            if field_name == "pk":
                return []
            try:
                obj.model._meta.get_field(field_name)
            except FieldDoesNotExist:
                return refer_to_missing_field(
                    field=field_name, option=label, obj=obj, id="admin.E033"
                )
            else:
                return []

    def _check_readonly_fields(self, obj):
        """Check that readonly_fields refers to proper attribute or field."""

        if obj.readonly_fields == ():
            return []
        elif not isinstance(obj.readonly_fields, (list, tuple)):
            return must_be(
                "a list or tuple", option="readonly_fields", obj=obj, id="admin.E034"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_readonly_fields_item(
                        obj, field_name, "readonly_fields[%d]" % index
                    )
                    for index, field_name in enumerate(obj.readonly_fields)
                )
            )

    def _check_readonly_fields_item(self, obj, field_name, label):
        if callable(field_name):
            return []
        elif hasattr(obj, field_name):
            return []
        elif hasattr(obj.model, field_name):
            return []
        else:
            try:
                obj.model._meta.get_field(field_name)
            except FieldDoesNotExist:
                return [
                    checks.Error(
                        "The value of '%s' is not a callable, an attribute of "
                        "'%s', or an attribute of '%s'."
                        % (
                            label,
                            obj.__class__.__name__,
                            obj.model._meta.label,
                        ),
                        obj=obj.__class__,
                        id="admin.E035",
                    )
                ]
            else:
                return []


class ModelAdminChecks(BaseModelAdminChecks):
    def check(self, admin_obj, **kwargs):
        return [
            *super().check(admin_obj),
            *self._check_save_as(admin_obj),
            *self._check_save_on_top(admin_obj),
            *self._check_inlines(admin_obj),
            *self._check_list_display(admin_obj),
            *self._check_list_display_links(admin_obj),
            *self._check_list_filter(admin_obj),
            *self._check_list_select_related(admin_obj),
            *self._check_list_per_page(admin_obj),
            *self._check_list_max_show_all(admin_obj),
            *self._check_list_editable(admin_obj),
            *self._check_search_fields(admin_obj),
            *self._check_date_hierarchy(admin_obj),
            *self._check_action_permission_methods(admin_obj),
            *self._check_actions_uniqueness(admin_obj),
        ]

    def _check_save_as(self, obj):
        """Check save_as is a boolean."""

        if not isinstance(obj.save_as, bool):
            return must_be("a boolean", option="save_as", obj=obj, id="admin.E101")
        else:
            return []

    def _check_save_on_top(self, obj):
        """Check save_on_top is a boolean."""

        if not isinstance(obj.save_on_top, bool):
            return must_be("a boolean", option="save_on_top", obj=obj, id="admin.E102")
        else:
            return []

    def _check_inlines(self, obj):
        """Check all inline model admin classes."""

        if not isinstance(obj.inlines, (list, tuple)):
            return must_be(
                "a list or tuple", option="inlines", obj=obj, id="admin.E103"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_inlines_item(obj, item, "inlines[%d]" % index)
                    for index, item in enumerate(obj.inlines)
                )
            )

    def _check_inlines_item(self, obj, inline, label):
        """Check one inline model admin."""
        try:
            inline_label = inline.__module__ + "." + inline.__name__
        except AttributeError:
            return [
                checks.Error(
                    "'%s' must inherit from 'InlineModelAdmin'." % obj,
                    obj=obj.__class__,
                    id="admin.E104",
                )
            ]

        from django.contrib.admin.options import InlineModelAdmin

        if not _issubclass(inline, InlineModelAdmin):
            return [
                checks.Error(
                    "'%s' must inherit from 'InlineModelAdmin'." % inline_label,
                    obj=obj.__class__,
                    id="admin.E104",
                )
            ]
        elif not inline.model:
            return [
                checks.Error(
                    "'%s' must have a 'model' attribute." % inline_label,
                    obj=obj.__class__,
                    id="admin.E105",
                )
            ]
        elif not _issubclass(inline.model, models.Model):
            return must_be(
                "a Model", option="%s.model" % inline_label, obj=obj, id="admin.E106"
            )
        else:
            return inline(obj.model, obj.admin_site).check()

    def _check_list_display(self, obj):
        """Check that list_display only contains fields or usable attributes."""

        if not isinstance(obj.list_display, (list, tuple)):
            return must_be(
                "a list or tuple", option="list_display", obj=obj, id="admin.E107"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_list_display_item(obj, item, "list_display[%d]" % index)
                    for index, item in enumerate(obj.list_display)
                )
            )

    # GEV-001 / GEV-002 / GEV-003 / GEV-004 / GEV-005 / GEV-006 —
    # architecture contract for list_display resolution.
    # ModelAdminChecks owns pre-request acceptance or rejection of each entry.
    # _check_list_display() is the sole inbound collection seam; admin.E108 and
    # admin.E109 are the existing outbound validation contracts.
    #
    # Resolution at this boundary may depend on the registered ModelAdmin's
    # namespace and the model class/_meta contract. It must not depend on a
    # model instance, ChangeList construction, or request-time rendering.
    # Accepted entries must remain compatible with the separate rendering
    # boundary owned by django.contrib.admin.utils.lookup_field().
    #
    # GEV-003 / GEV-004 add a second downstream compatibility boundary:
    # django.contrib.admin.utils.label_for_field() owns changelist label
    # resolution. Options.get_field() remains only the metadata-discovery port;
    # a value returned by it is not, by itself, a valid list_display contract.
    # Dependency direction is ModelAdminChecks -> existing admin.utils lookup
    # contracts. The utilities and model metadata must not depend on checks or
    # acquire responsibility for emitting admin.E108.
    #
    # GEV-005 / GEV-006 preserve the existing accepted-reference ports at this
    # seam: model field metadata, the ModelAdmin namespace, the model namespace,
    # and callable entries. ModelAdminChecks owns their validation composition;
    # each provider continues to own only its field, attribute, or callable.
    # No adapter or public contract is required between these existing owners.
    # Dependency direction remains checks -> ModelAdmin/model metadata/model
    # namespace, while accepted values flow onward through the unchanged admin
    # rendering utilities. Field-kind rejection remains the separate admin.E109
    # contract and must not be folded into unresolved-reference admin.E108.
    #
    # Verification ownership remains in ListDisplayTests:
    # - GEV-001: unresolvable model/ModelAdmin entries reach admin.E108 here.
    # - GEV-002: the reverse query name "choice" reaches admin.E108 here.
    # - GEV-003: a metadata-only reverse relation reaches admin.E108 here.
    # - GEV-004: a metadata-only many-to-many related name reaches admin.E108 here.
    # - GEV-005: valid model fields remain accepted without admin.E108 here.
    # - GEV-006: valid callable, model attribute, and ModelAdmin attribute entries
    #   remain accepted without admin.E108 here.
    def _check_list_display_item(self, obj, item, label):
        # GEV-005 / GEV-006 — preserve every supported list_display reference.
        # Logic obligations and verification loci:
        # - GEV-005 maps to
        #   test_gev_005_valid_model_field_passes_list_display_check_without_e108.
        # - GEV-006 callable maps to
        #   test_gev_006_valid_callable_passes_list_display_check_without_e108.
        # - GEV-006 model attribute maps to
        #   test_gev_006_valid_model_attribute_passes_list_display_check_without_e108.
        # - GEV-006 ModelAdmin attribute maps to
        #   test_gev_006_valid_modeladmin_attribute_passes_list_display_check_without_e108.
        #
        # INPUT: the registered ModelAdmin and one candidate list_display entry.
        # RESOLUTION PROCEDURE:
        # 1. If the entry itself is callable, transition CANDIDATE -> CALLABLE ->
        #    ACCEPTED and return no error (GEV-006).
        # 2. Otherwise, if the ModelAdmin exposes the named entry, transition
        #    CANDIDATE -> MODELADMIN_ATTRIBUTE -> ACCEPTED and return no error
        #    (GEV-006).
        # 3. Otherwise, ask model metadata for the named field. If a field is found,
        #    transition CANDIDATE -> MODEL_FIELD, then apply the existing
        #    displayability boundary. A displayable field must not emit admin.E108
        #    (GEV-005); a metadata-only name continues through the GEV-003/GEV-004
        #    compatibility decision below.
        # 4. If model metadata reports no field, ask the model namespace for the
        #    named attribute. If present, transition CANDIDATE -> MODEL_ATTRIBUTE ->
        #    ACCEPTED and return no error after applicable field-kind checks
        #    (GEV-006).
        # 5. Only if both model metadata and the model namespace reject the name may
        #    the entry transition CANDIDATE -> UNRESOLVED -> REJECTED_E108.
        # 6. For a resolved model field, preserve the separate field-kind decision:
        #    prohibited many-to-many/reverse-foreign-key fields follow admin.E109;
        #    every other valid field transitions MODEL_FIELD -> ACCEPTED with no
        #    admin.E108 (GEV-005).
        # OUTPUT: supported references produce no admin.E108; unsupported names
        # alone enter the existing admin.E108 failure path.
        # GEV-001 / GEV-002 — list_display check-time resolution parity.
        # Logic obligations:
        # - GEV-001 maps to
        #   test_gev_001_unresolvable_model_or_modeladmin_entry_emits_e108_at_check_time.
        # - GEV-002 maps to
        #   test_gev_002_questionadmin_choice_entry_emits_e108_before_changelist_request.
        #
        # INPUT: the registered ModelAdmin, one list_display entry, and its label.
        # PROCEDURE:
        # 1. If the entry is callable, accept it and stop.
        # 2. Otherwise, if the ModelAdmin exposes the named entry, accept it and stop.
        # 3. Otherwise, resolve the name against both the registered model's usable
        #    attributes and its field metadata, applying the same accessibility rule
        #    that changelist value lookup will apply to a model instance.
        # 4. If neither source yields a renderable value, emit admin.E108 naming the
        #    entry and stop; do not defer this failure to a changelist request.
        # 5. In particular, if metadata resolves a reverse relation only by its query
        #    name but that name is not accessible on model instances, treat it as
        #    unresolvable. Thus QuestionAdmin.list_display = ["choice"] transitions
        #    directly to admin.E108 during system checks.
        # 6. If the entry is renderable but its resolved field kind is prohibited for
        #    list_display, continue through the existing field-kind error path;
        #    otherwise accept it.
        # OUTPUT: either no errors or the deterministic check error for this entry.
        #
        # GEV-003 / GEV-004 — metadata presence is not displayability.
        # Logic obligations:
        # - GEV-003 maps to
        #   test_gev_003_metadata_only_reverse_relation_unresolved_by_label_emits_e108.
        # - GEV-004 maps to
        #   test_gev_004_metadata_only_m2m_related_name_unresolved_by_label_emits_e108.
        #
        # PROCEDURE FOR A NAME FOUND ONLY IN MODEL METADATA:
        # 1. Treat metadata discovery as a provisional resolution, not acceptance.
        # 2. Determine whether changelist field-label lookup can resolve the same
        #    name from the registered model and ModelAdmin namespaces.
        # 3. If label lookup cannot resolve the name, transition
        #    CANDIDATE -> METADATA_ONLY -> LABEL_UNRESOLVABLE -> REJECTED_E108.
        # 4. Apply that transition independently when the metadata object represents
        #    a reverse relation (GEV-003) or a many-to-many relation (GEV-004).
        # 5. Emit exactly one admin.E108 for the entry and stop; metadata relation
        #    kind alone must not redirect this failure to admin.E109.
        # 6. Only when label lookup resolves the name may later field-kind checks
        #    determine whether another existing validation outcome applies.
        if callable(item):
            return []
        elif hasattr(obj, item):
            return []
        try:
            field = obj.model._meta.get_field(item)
        except FieldDoesNotExist:
            try:
                field = getattr(obj.model, item)
            except AttributeError:
                return [
                    checks.Error(
                        "The value of '%s' refers to '%s', which is not a "
                        "callable, an attribute of '%s', or an attribute or "
                        "method on '%s'."
                        % (
                            label,
                            item,
                            obj.__class__.__name__,
                            obj.model._meta.label,
                        ),
                        obj=obj.__class__,
                        id="admin.E108",
                    )
                ]
        else:
            # GEV-001 / GEV-002 / GEV-003 / GEV-004: A name found only in
            # model metadata must also be resolvable by changelist label
            # lookup. In particular, reverse relations can be addressable by
            # their query name in Options.get_field() without being available
            # from the model namespace used by the changelist.
            if not hasattr(obj.model, item):
                try:
                    label_for_field(item, obj.model, obj)
                except AttributeError:
                    return [
                        checks.Error(
                            "The value of '%s' refers to '%s', which is not a "
                            "callable, an attribute of '%s', or an attribute or "
                            "method on '%s'."
                            % (
                                label,
                                item,
                                obj.__class__.__name__,
                                obj.model._meta.label,
                            ),
                            obj=obj.__class__,
                            id="admin.E108",
                        )
                    ]
        if isinstance(field, models.ManyToManyField) or (
            getattr(field, "rel", None) and field.rel.field.many_to_one
        ):
            return [
                checks.Error(
                    f"The value of '{label}' must not be a many-to-many field or a "
                    f"reverse foreign key.",
                    obj=obj.__class__,
                    id="admin.E109",
                )
            ]
        return []

    def _check_list_display_links(self, obj):
        """Check that list_display_links is a unique subset of list_display."""
        from django.contrib.admin.options import ModelAdmin

        if obj.list_display_links is None:
            return []
        elif not isinstance(obj.list_display_links, (list, tuple)):
            return must_be(
                "a list, a tuple, or None",
                option="list_display_links",
                obj=obj,
                id="admin.E110",
            )
        # Check only if ModelAdmin.get_list_display() isn't overridden.
        elif obj.get_list_display.__func__ is ModelAdmin.get_list_display:
            return list(
                chain.from_iterable(
                    self._check_list_display_links_item(
                        obj, field_name, "list_display_links[%d]" % index
                    )
                    for index, field_name in enumerate(obj.list_display_links)
                )
            )
        return []

    def _check_list_display_links_item(self, obj, field_name, label):
        if field_name not in obj.list_display:
            return [
                checks.Error(
                    "The value of '%s' refers to '%s', which is not defined in "
                    "'list_display'." % (label, field_name),
                    obj=obj.__class__,
                    id="admin.E111",
                )
            ]
        else:
            return []

    def _check_list_filter(self, obj):
        if not isinstance(obj.list_filter, (list, tuple)):
            return must_be(
                "a list or tuple", option="list_filter", obj=obj, id="admin.E112"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_list_filter_item(obj, item, "list_filter[%d]" % index)
                    for index, item in enumerate(obj.list_filter)
                )
            )

    def _check_list_filter_item(self, obj, item, label):
        """
        Check one item of `list_filter`, i.e. check if it is one of three options:
        1. 'field' -- a basic field filter, possibly w/ relationships (e.g.
           'field__rel')
        2. ('field', SomeFieldListFilter) - a field-based list filter class
        3. SomeListFilter - a non-field list filter class
        """
        from django.contrib.admin import FieldListFilter, ListFilter

        if callable(item) and not isinstance(item, models.Field):
            # If item is option 3, it should be a ListFilter...
            if not _issubclass(item, ListFilter):
                return must_inherit_from(
                    parent="ListFilter", option=label, obj=obj, id="admin.E113"
                )
            # ...  but not a FieldListFilter.
            elif issubclass(item, FieldListFilter):
                return [
                    checks.Error(
                        "The value of '%s' must not inherit from 'FieldListFilter'."
                        % label,
                        obj=obj.__class__,
                        id="admin.E114",
                    )
                ]
            else:
                return []
        elif isinstance(item, (tuple, list)):
            # item is option #2
            field, list_filter_class = item
            if not _issubclass(list_filter_class, FieldListFilter):
                return must_inherit_from(
                    parent="FieldListFilter",
                    option="%s[1]" % label,
                    obj=obj,
                    id="admin.E115",
                )
            else:
                return []
        else:
            # item is option #1
            field = item

            # Validate the field string
            try:
                get_fields_from_path(obj.model, field)
            except (NotRelationField, FieldDoesNotExist):
                return [
                    checks.Error(
                        "The value of '%s' refers to '%s', which does not refer to a "
                        "Field." % (label, field),
                        obj=obj.__class__,
                        id="admin.E116",
                    )
                ]
            else:
                return []

    def _check_list_select_related(self, obj):
        """Check that list_select_related is a boolean, a list or a tuple."""

        if not isinstance(obj.list_select_related, (bool, list, tuple)):
            return must_be(
                "a boolean, tuple or list",
                option="list_select_related",
                obj=obj,
                id="admin.E117",
            )
        else:
            return []

    def _check_list_per_page(self, obj):
        """Check that list_per_page is an integer."""

        if not isinstance(obj.list_per_page, int):
            return must_be(
                "an integer", option="list_per_page", obj=obj, id="admin.E118"
            )
        else:
            return []

    def _check_list_max_show_all(self, obj):
        """Check that list_max_show_all is an integer."""

        if not isinstance(obj.list_max_show_all, int):
            return must_be(
                "an integer", option="list_max_show_all", obj=obj, id="admin.E119"
            )
        else:
            return []

    def _check_list_editable(self, obj):
        """Check that list_editable is a sequence of editable fields from
        list_display without first element."""

        if not isinstance(obj.list_editable, (list, tuple)):
            return must_be(
                "a list or tuple", option="list_editable", obj=obj, id="admin.E120"
            )
        else:
            return list(
                chain.from_iterable(
                    self._check_list_editable_item(
                        obj, item, "list_editable[%d]" % index
                    )
                    for index, item in enumerate(obj.list_editable)
                )
            )

    def _check_list_editable_item(self, obj, field_name, label):
        try:
            field = obj.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return refer_to_missing_field(
                field=field_name, option=label, obj=obj, id="admin.E121"
            )
        else:
            if field_name not in obj.list_display:
                return [
                    checks.Error(
                        "The value of '%s' refers to '%s', which is not "
                        "contained in 'list_display'." % (label, field_name),
                        obj=obj.__class__,
                        id="admin.E122",
                    )
                ]
            elif obj.list_display_links and field_name in obj.list_display_links:
                return [
                    checks.Error(
                        "The value of '%s' cannot be in both 'list_editable' and "
                        "'list_display_links'." % field_name,
                        obj=obj.__class__,
                        id="admin.E123",
                    )
                ]
            # If list_display[0] is in list_editable, check that
            # list_display_links is set. See #22792 and #26229 for use cases.
            elif (
                obj.list_display[0] == field_name
                and not obj.list_display_links
                and obj.list_display_links is not None
            ):
                return [
                    checks.Error(
                        "The value of '%s' refers to the first field in 'list_display' "
                        "('%s'), which cannot be used unless 'list_display_links' is "
                        "set." % (label, obj.list_display[0]),
                        obj=obj.__class__,
                        id="admin.E124",
                    )
                ]
            elif not field.editable or field.primary_key:
                return [
                    checks.Error(
                        "The value of '%s' refers to '%s', which is not editable "
                        "through the admin." % (label, field_name),
                        obj=obj.__class__,
                        id="admin.E125",
                    )
                ]
            else:
                return []

    def _check_search_fields(self, obj):
        """Check search_fields is a sequence."""

        if not isinstance(obj.search_fields, (list, tuple)):
            return must_be(
                "a list or tuple", option="search_fields", obj=obj, id="admin.E126"
            )
        else:
            return []

    def _check_date_hierarchy(self, obj):
        """Check that date_hierarchy refers to DateField or DateTimeField."""

        if obj.date_hierarchy is None:
            return []
        else:
            try:
                field = get_fields_from_path(obj.model, obj.date_hierarchy)[-1]
            except (NotRelationField, FieldDoesNotExist):
                return [
                    checks.Error(
                        "The value of 'date_hierarchy' refers to '%s', which "
                        "does not refer to a Field." % obj.date_hierarchy,
                        obj=obj.__class__,
                        id="admin.E127",
                    )
                ]
            else:
                if not isinstance(field, (models.DateField, models.DateTimeField)):
                    return must_be(
                        "a DateField or DateTimeField",
                        option="date_hierarchy",
                        obj=obj,
                        id="admin.E128",
                    )
                else:
                    return []

    def _check_action_permission_methods(self, obj):
        """
        Actions with an allowed_permission attribute require the ModelAdmin to
        implement a has_<perm>_permission() method for each permission.
        """
        actions = obj._get_base_actions()
        errors = []
        for func, name, _ in actions:
            if not hasattr(func, "allowed_permissions"):
                continue
            for permission in func.allowed_permissions:
                method_name = "has_%s_permission" % permission
                if not hasattr(obj, method_name):
                    errors.append(
                        checks.Error(
                            "%s must define a %s() method for the %s action."
                            % (
                                obj.__class__.__name__,
                                method_name,
                                func.__name__,
                            ),
                            obj=obj.__class__,
                            id="admin.E129",
                        )
                    )
        return errors

    def _check_actions_uniqueness(self, obj):
        """Check that every action has a unique __name__."""
        errors = []
        names = collections.Counter(name for _, name, _ in obj._get_base_actions())
        for name, count in names.items():
            if count > 1:
                errors.append(
                    checks.Error(
                        "__name__ attributes of actions defined in %s must be "
                        "unique. Name %r is not unique."
                        % (
                            obj.__class__.__name__,
                            name,
                        ),
                        obj=obj.__class__,
                        id="admin.E130",
                    )
                )
        return errors


class InlineModelAdminChecks(BaseModelAdminChecks):
    def check(self, inline_obj, **kwargs):
        parent_model = inline_obj.parent_model
        return [
            *super().check(inline_obj),
            *self._check_relation(inline_obj, parent_model),
            *self._check_exclude_of_parent_model(inline_obj, parent_model),
            *self._check_extra(inline_obj),
            *self._check_max_num(inline_obj),
            *self._check_min_num(inline_obj),
            *self._check_formset(inline_obj),
        ]

    def _check_exclude_of_parent_model(self, obj, parent_model):
        # Do not perform more specific checks if the base checks result in an
        # error.
        errors = super()._check_exclude(obj)
        if errors:
            return []

        # Skip if `fk_name` is invalid.
        if self._check_relation(obj, parent_model):
            return []

        if obj.exclude is None:
            return []

        fk = _get_foreign_key(parent_model, obj.model, fk_name=obj.fk_name)
        if fk.name in obj.exclude:
            return [
                checks.Error(
                    "Cannot exclude the field '%s', because it is the foreign key "
                    "to the parent model '%s'."
                    % (
                        fk.name,
                        parent_model._meta.label,
                    ),
                    obj=obj.__class__,
                    id="admin.E201",
                )
            ]
        else:
            return []

    def _check_relation(self, obj, parent_model):
        try:
            _get_foreign_key(parent_model, obj.model, fk_name=obj.fk_name)
        except ValueError as e:
            return [checks.Error(e.args[0], obj=obj.__class__, id="admin.E202")]
        else:
            return []

    def _check_extra(self, obj):
        """Check that extra is an integer."""

        if not isinstance(obj.extra, int):
            return must_be("an integer", option="extra", obj=obj, id="admin.E203")
        else:
            return []

    def _check_max_num(self, obj):
        """Check that max_num is an integer."""

        if obj.max_num is None:
            return []
        elif not isinstance(obj.max_num, int):
            return must_be("an integer", option="max_num", obj=obj, id="admin.E204")
        else:
            return []

    def _check_min_num(self, obj):
        """Check that min_num is an integer."""

        if obj.min_num is None:
            return []
        elif not isinstance(obj.min_num, int):
            return must_be("an integer", option="min_num", obj=obj, id="admin.E205")
        else:
            return []

    def _check_formset(self, obj):
        """Check formset is a subclass of BaseModelFormSet."""

        if not _issubclass(obj.formset, BaseModelFormSet):
            return must_inherit_from(
                parent="BaseModelFormSet", option="formset", obj=obj, id="admin.E206"
            )
        else:
            return []


def must_be(type, option, obj, id):
    return [
        checks.Error(
            "The value of '%s' must be %s." % (option, type),
            obj=obj.__class__,
            id=id,
        ),
    ]


def must_inherit_from(parent, option, obj, id):
    return [
        checks.Error(
            "The value of '%s' must inherit from '%s'." % (option, parent),
            obj=obj.__class__,
            id=id,
        ),
    ]


def refer_to_missing_field(field, option, obj, id):
    return [
        checks.Error(
            "The value of '%s' refers to '%s', which is not a field of '%s'."
            % (option, field, obj.model._meta.label),
            obj=obj.__class__,
            id=id,
        ),
    ]
