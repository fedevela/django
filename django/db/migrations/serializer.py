from importlib import import_module

import builtins
import collections.abc
import datetime
import decimal
import enum
import functools
import math
import re
import types
import uuid

from django.conf import SettingsReference
from django.db import models
from django.db.migrations.operations.base import Operation
from django.db.migrations.utils import COMPILED_REGEX_TYPE, RegexObject
from django.utils.functional import LazyObject, Promise
from django.utils.timezone import utc
from django.utils.version import get_docs_version


class BaseSerializer:
    def __init__(self, value):
        self.value = value

    def serialize(self):
        raise NotImplementedError('Subclasses of BaseSerializer must implement the serialize() method.')


class BaseSequenceSerializer(BaseSerializer):
    def _format(self):
        raise NotImplementedError('Subclasses of BaseSequenceSerializer must implement the _format() method.')

    def serialize(self):
        imports = set()
        strings = []
        for item in self.value:
            item_string, item_imports = serializer_factory(item).serialize()
            imports.update(item_imports)
            strings.append(item_string)
        value = self._format()
        return value % (", ".join(strings)), imports


class BaseSimpleSerializer(BaseSerializer):
    def serialize(self):
        return repr(self.value), set()


class ChoicesSerializer(BaseSerializer):
    def serialize(self):
        return serializer_factory(self.value.value).serialize()


class DateTimeSerializer(BaseSerializer):
    """For datetime.*, except datetime.datetime."""
    def serialize(self):
        return repr(self.value), {'import datetime'}


class DatetimeDatetimeSerializer(BaseSerializer):
    """For datetime.datetime."""
    def serialize(self):
        if self.value.tzinfo is not None and self.value.tzinfo != utc:
            self.value = self.value.astimezone(utc)
        imports = ["import datetime"]
        if self.value.tzinfo is not None:
            imports.append("from django.utils.timezone import utc")
        return repr(self.value).replace('<UTC>', 'utc'), set(imports)


class DecimalSerializer(BaseSerializer):
    def serialize(self):
        return repr(self.value), {"from decimal import Decimal"}


class DeconstructableSerializer(BaseSerializer):
    @staticmethod
    def serialize_deconstructed(path, args, kwargs):
        # M154-005: Serialize a deconstructible value as a deterministic function-shape call.
        # INPUTS:
        # - deconstructed path from .deconstruct()
        # - positional args (ordered by declaration for the target class)
        # - kwargs (declared semantics may be unordered; sort at output boundary)
        # PROCEDURE:
        # 1) Resolve the stable textual path using _serialize_path(path) once.
        # 2) Serialize args in declaration order.
        # 3) Serialize kwargs in sorted key order to keep call text stable.
        # 4) Emit "%s(%s)" with positional and kwarg segments joined by ", ".
        # FAILURE:
        # - No explicit recovery: callers propagate serializer errors from _serialize_path.
        name, imports = DeconstructableSerializer._serialize_path(path)
        strings = []
        for arg in args:
            arg_string, arg_imports = serializer_factory(arg).serialize()
            strings.append(arg_string)
            imports.update(arg_imports)
        for kw, arg in sorted(kwargs.items()):
            arg_string, arg_imports = serializer_factory(arg).serialize()
            imports.update(arg_imports)
            strings.append("%s=%s" % (kw, arg_string))
        return "%s(%s)" % (name, ", ".join(strings)), imports

    @staticmethod
    def _serialize_path(path):
        # M154-003 (top-level path invariance):
        # - Keep top-level deconstructible targets unchanged (e.g. "module.TopLevelField").
        # M154-005 (nested reference determinism):
        # - Resolve every dotted path via the same canonical scan to force identical
        #   output shape across repeated references and field reorderings.
        #
        # INPUT:
        # - path: dotted deconstruct token from value.deconstruct().
        # STATE:
        # - parts : split components of path.
        # - module/name : mutable resolution output.
        # TRANSITION loop:
        # for split_point from len(parts)-1 down to 1:
        #   module_candidate = ".".join(parts[:split_point])
        #   attr_chain = parts[split_point:]
        #   try import module_candidate:
        #       iterate attr_chain over imported module object
        #       if any attr missing -> candidate rejected
        #       if full attr_chain resolves -> first successful candidate wins
        #           module = module_candidate; name = ".".join(attr_chain); break
        #   except ImportError: continue
        # FALLBACK:
        # - if no candidate resolves, retain default split result.
        # OUTPUT:
        # - For django.db.models target, emit "models.<name>" with models import.
        # - Else emit "<module>.<name>" and "import <module>".
        # INVARIANTS:
        # - Longest-prefix-first scan is deterministic for repeated calls.
        # - On module-level objects, first valid prefix is the module itself, so no
        #   nested rewrite occurs.
        parts = path.split(".")
        module = ".".join(parts[:-1])
        name = parts[-1]
        for split_point in range(len(parts) - 1, 0, -1):
            module_candidate = ".".join(parts[:split_point])
            attr_candidate = parts[split_point:]
            try:
                module_obj = import_module(module_candidate)
            except ImportError:
                continue
            for part in attr_candidate:
                if not hasattr(module_obj, part):
                    break
                module_obj = getattr(module_obj, part)
            else:
                module = module_candidate
                name = ".".join(attr_candidate)
                break

        if module == "django.db.models":
            imports = {"from django.db import models"}
            name = "models.%s" % name
        else:
            imports = {"import %s" % module}
            name = "%s.%s" % (module, name)
        return name, imports

    def serialize(self):
        return self.serialize_deconstructed(*self.value.deconstruct())


class DictionarySerializer(BaseSerializer):
    def serialize(self):
        imports = set()
        strings = []
        for k, v in sorted(self.value.items()):
            k_string, k_imports = serializer_factory(k).serialize()
            v_string, v_imports = serializer_factory(v).serialize()
            imports.update(k_imports)
            imports.update(v_imports)
            strings.append((k_string, v_string))
        return "{%s}" % (", ".join("%s: %s" % (k, v) for k, v in strings)), imports


class EnumSerializer(BaseSerializer):
    def serialize(self):
        enum_class = self.value.__class__
        module = enum_class.__module__
        return (
            '%s.%s[%r]' % (module, enum_class.__qualname__, self.value.name),
            {'import %s' % module},
        )


class FloatSerializer(BaseSimpleSerializer):
    def serialize(self):
        if math.isnan(self.value) or math.isinf(self.value):
            return 'float("{}")'.format(self.value), set()
        return super().serialize()


class FrozensetSerializer(BaseSequenceSerializer):
    def _format(self):
        return "frozenset([%s])"


class FunctionTypeSerializer(BaseSerializer):
    def serialize(self):
        if getattr(self.value, "__self__", None) and isinstance(self.value.__self__, type):
            klass = self.value.__self__
            module = klass.__module__
            return "%s.%s.%s" % (module, klass.__name__, self.value.__name__), {"import %s" % module}
        # Further error checking
        if self.value.__name__ == '<lambda>':
            raise ValueError("Cannot serialize function: lambda")
        if self.value.__module__ is None:
            raise ValueError("Cannot serialize function %r: No module" % self.value)

        module_name = self.value.__module__

        if '<' not in self.value.__qualname__:  # Qualname can include <locals>
            return '%s.%s' % (module_name, self.value.__qualname__), {'import %s' % self.value.__module__}

        raise ValueError(
            'Could not find function %s in %s.\n' % (self.value.__name__, module_name)
        )


class FunctoolsPartialSerializer(BaseSerializer):
    def serialize(self):
        # Serialize functools.partial() arguments
        func_string, func_imports = serializer_factory(self.value.func).serialize()
        args_string, args_imports = serializer_factory(self.value.args).serialize()
        keywords_string, keywords_imports = serializer_factory(self.value.keywords).serialize()
        # Add any imports needed by arguments
        imports = {'import functools', *func_imports, *args_imports, *keywords_imports}
        return (
            'functools.%s(%s, *%s, **%s)' % (
                self.value.__class__.__name__,
                func_string,
                args_string,
                keywords_string,
            ),
            imports,
        )


class IterableSerializer(BaseSerializer):
    def serialize(self):
        imports = set()
        strings = []
        for item in self.value:
            item_string, item_imports = serializer_factory(item).serialize()
            imports.update(item_imports)
            strings.append(item_string)
        # When len(strings)==0, the empty iterable should be serialized as
        # "()", not "(,)" because (,) is invalid Python syntax.
        value = "(%s)" if len(strings) != 1 else "(%s,)"
        return value % (", ".join(strings)), imports


class ModelFieldSerializer(DeconstructableSerializer):
    def serialize(self):
        attr_name, path, args, kwargs = self.value.deconstruct()
        return self.serialize_deconstructed(path, args, kwargs)


class ModelManagerSerializer(DeconstructableSerializer):
    def serialize(self):
        as_manager, manager_path, qs_path, args, kwargs = self.value.deconstruct()
        if as_manager:
            name, imports = self._serialize_path(qs_path)
            return "%s.as_manager()" % name, imports
        else:
            return self.serialize_deconstructed(manager_path, args, kwargs)


class OperationSerializer(BaseSerializer):
    def serialize(self):
        from django.db.migrations.writer import OperationWriter
        string, imports = OperationWriter(self.value, indentation=0).serialize()
        # Nested operation, trailing comma is handled in upper OperationWriter._write()
        return string.rstrip(','), imports


class RegexSerializer(BaseSerializer):
    def serialize(self):
        regex_pattern, pattern_imports = serializer_factory(self.value.pattern).serialize()
        # Turn off default implicit flags (e.g. re.U) because regexes with the
        # same implicit and explicit flags aren't equal.
        flags = self.value.flags ^ re.compile('').flags
        regex_flags, flag_imports = serializer_factory(flags).serialize()
        imports = {'import re', *pattern_imports, *flag_imports}
        args = [regex_pattern]
        if flags:
            args.append(regex_flags)
        return "re.compile(%s)" % ', '.join(args), imports


class SequenceSerializer(BaseSequenceSerializer):
    def _format(self):
        return "[%s]"


class SetSerializer(BaseSequenceSerializer):
    def _format(self):
        # Serialize as a set literal except when value is empty because {}
        # is an empty dict.
        return '{%s}' if self.value else 'set(%s)'


class SettingsReferenceSerializer(BaseSerializer):
    def serialize(self):
        return "settings.%s" % self.value.setting_name, {"from django.conf import settings"}


class TupleSerializer(BaseSequenceSerializer):
    def _format(self):
        # When len(value)==0, the empty tuple should be serialized as "()",
        # not "(,)" because (,) is invalid Python syntax.
        return "(%s)" if len(self.value) != 1 else "(%s,)"


class TypeSerializer(BaseSerializer):
    def serialize(self):
        special_cases = [
            (models.Model, "models.Model", []),
            (type(None), 'type(None)', []),
        ]
        for case, string, imports in special_cases:
            if case is self.value:
                return string, set(imports)
        if hasattr(self.value, "__module__"):
            module = self.value.__module__
            if module == builtins.__name__:
                return self.value.__name__, set()
            candidate = "%s.%s" % (module, self.value.__qualname__)
            value = self.value
            module_object = import_module(module)
            for attr in value.__qualname__.split("."):
                if not hasattr(module_object, attr):
                    raise ValueError(
                        "Could not find class %s in %s.\nPlease note that you cannot serialize "
                        "local class scope objects. Please move the class into the module "
                        "body to use migrations.\nFor more information, see "
                        "https://docs.djangoproject.com/en/%s/topics/migrations/#migration-serializing\n"
                        % (value.__name__, module, get_docs_version())
                    )
                module_object = getattr(module_object, attr)
            if module_object is not value:
                raise ValueError(
                    "Could not find class %s in %s.\nPlease note that you cannot serialize "
                    "local class scope objects. Please move the class into the module "
                    "body to use migrations.\nFor more information, see "
                    "https://docs.djangoproject.com/en/%s/topics/migrations/#migration-serializing\n"
                    % (value.__name__, module, get_docs_version())
                )
            return candidate, {"import %s" % module}
        raise TypeError("Cannot serialize: %r" % self.value)


class UUIDSerializer(BaseSerializer):
    def serialize(self):
        return "uuid.%s" % repr(self.value), {"import uuid"}


class Serializer:
    _registry = {
        # Some of these are order-dependent.
        frozenset: FrozensetSerializer,
        list: SequenceSerializer,
        set: SetSerializer,
        tuple: TupleSerializer,
        dict: DictionarySerializer,
        models.Choices: ChoicesSerializer,
        enum.Enum: EnumSerializer,
        datetime.datetime: DatetimeDatetimeSerializer,
        (datetime.date, datetime.timedelta, datetime.time): DateTimeSerializer,
        SettingsReference: SettingsReferenceSerializer,
        float: FloatSerializer,
        (bool, int, type(None), bytes, str, range): BaseSimpleSerializer,
        decimal.Decimal: DecimalSerializer,
        (functools.partial, functools.partialmethod): FunctoolsPartialSerializer,
        (types.FunctionType, types.BuiltinFunctionType, types.MethodType): FunctionTypeSerializer,
        collections.abc.Iterable: IterableSerializer,
        (COMPILED_REGEX_TYPE, RegexObject): RegexSerializer,
        uuid.UUID: UUIDSerializer,
    }

    @classmethod
    def register(cls, type_, serializer):
        if not issubclass(serializer, BaseSerializer):
            raise ValueError("'%s' must inherit from 'BaseSerializer'." % serializer.__name__)
        cls._registry[type_] = serializer

    @classmethod
    def unregister(cls, type_):
        cls._registry.pop(type_)


def serializer_factory(value):
    if isinstance(value, Promise):
        value = str(value)
    elif isinstance(value, LazyObject):
        # The unwrapped value is returned as the first item of the arguments
        # tuple.
        value = value.__reduce__()[1][0]

    if isinstance(value, models.Field):
        return ModelFieldSerializer(value)
    if isinstance(value, models.manager.BaseManager):
        return ModelManagerSerializer(value)
    if isinstance(value, Operation):
        return OperationSerializer(value)
    # M154-002 / M154-004: class objects are intentionally handled here
    # before generic deconstructable fallback so nested class arguments follow
    # TypeSerializer's path-serialization obligations and stability checks.
    if isinstance(value, type):
        return TypeSerializer(value)
    # Anything that knows how to deconstruct itself.
    if hasattr(value, 'deconstruct'):
        return DeconstructableSerializer(value)
    for type_, serializer_cls in Serializer._registry.items():
        if isinstance(value, type_):
            return serializer_cls(value)
    raise ValueError(
        "Cannot serialize: %r\nThere are some values Django cannot serialize into "
        "migration files.\nFor more, see https://docs.djangoproject.com/en/%s/"
        "topics/migrations/#migration-serializing" % (value, get_docs_version())
    )
