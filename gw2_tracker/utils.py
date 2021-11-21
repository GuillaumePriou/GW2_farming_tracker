from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, Iterable, TypeAlias, TypeVar, overload

Cls = TypeVar("Cls", bound=type)

JsonValue: TypeAlias = None | bool | int | float | str
JsonArray: TypeAlias = list["AnyJson"]
JsonObject: TypeAlias = dict[str, "AnyJson"]
AnyJson: TypeAlias = JsonValue | JsonArray | JsonObject

AttrClass: TypeAlias = type

from collections import abc

import attr


def required_attrs(*attributes: str):
    """
    Method decorator to require attributes to be defined on the instance
    """
    attrs = list(attributes)

    def wrapper_factory(method):
        @functools.wraps(method)
        def wrapped_method(self, *args, **kwargs):
            missing = [attr for attr in attrs if getattr(self, attr) is None]
            if missing:
                raise AttributeError(
                    f"Method {method.__name__} requires attributes " + " ".join(missing)
                )
            return method(self, *args, **kwargs)

        return wrapped_method

    return wrapper_factory


@overload
def autoformat(
    cls: None, /, params: str | Iterable[str] = ("message", "msg")
) -> Callable[[Cls], Cls]:
    ...


@overload
def autoformat(cls: Cls, /, params: str | Iterable[str] = ("message", "msg")) -> Cls:
    ...


def autoformat(cls, /, params=("message", "msg")):
    """
    Class decorator to autoformat string arguments in the __init__ method

    Wraps the class ``__init__`` method such that parameters specified in `params`
    are formatted using `str.format` with all other parameters passed to
    `str.format` with the same name as found in ``__init__``, before passing
    them to the original ``__init__``.
    This is useful for exceptions to automatically format the exception's message.

    Arguments:
        params: names of the parameters to convert to string and format

    Usage:
        @autoformat
        class MyException(Exception):
            def __init__(self, elem, msg="{elem} is invalid"):
                super().__init__(msg)
                self.msg = msg
                self.elem = elem

        assert MyException(8).msg == "8 is invalid"
    """
    if isinstance(params, str):
        params = (params,)

    def decorator(cls: Cls) -> Cls:
        init = cls.__init__
        sig = inspect.signature(init)
        params_to_format = sig.parameters.keys() & set(params)

        @functools.wraps(init)
        def __init__(*args, **kwargs):
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            args_to_format = {
                name: bound_args.arguments.pop(name)
                for name in params_to_format
                if name in bound_args.arguments
            }
            formatted_args = {
                name: str(arg).format(**bound_args.arguments)
                for name, arg in args_to_format.items()
            }
            for name, arg in formatted_args.items():
                bound_args.arguments[name] = arg

            return init(*bound_args.args, **bound_args.kwargs)

        setattr(cls, "__init__", __init__)
        return cls

    if cls is None:
        return decorator
    elif isinstance(cls, type):
        return decorator(cls)
    else:
        raise TypeError(f"@autoformat is a class decorator, cannot decorate {cls}")


def jsonize(inst, *, ignore: abc.Container[str] = ()) -> dict[str, Any]:
    """
    Recursively serialize an attr instance to JSON.

    Serialize an attr instance to JSON by returning a dictionary of fields
    values. If a field value has the ``to_json`` method, it is called to get
    its json serialization, otherwise the value is left as-is.

    This is intended as a helper to implement a ``to_json`` method on attr
    classes, which may defer to this function.

    Arguments:
        instance: attr class instance to serialize to json
        ignore: field name to ignore and leave out of the serialization

    Returns:
        The json serialization of instance. All values may not be valid
        json values, depending on the fields type.

    Raises:
        attr.NotAnAttrsClassError: instance is not an instance of an attr class
        AttributeError: if a field is not found on instance

    See also:
        unjsonize
    """
    cls = type(inst)
    cls_fields = attr.fields(cls)

    def filter(field: attr.Attribute, value: Any):
        return not (field in cls_fields and field.name in ignore)

    def serializer(instance, field: attr.Attribute, value):
        if hasattr(value, "to_json"):
            return value.to_json()
        return value

    return attr.asdict(inst, recurse=True, filter=filter, value_serializer=serializer)
    return {
        f.name: value.to_json()
        if hasattr((value := getattr(instance, f.name)), "to_json")
        else value
        for f in attr.fields(type(instance))
        if f.name not in ignore
    }


def unjsonize(
    cls: AttrClass, obj: JsonObject, *, ignore: abc.Container[str] = ()
) -> dict[str, Any]:
    """
    Deserialize an attr class from json format.

    Deserialize an attr class from the json format. This is the inverse
    operation from `jsonize`, with the some caveats.

    First, only fields whose type is exactly a class will be checked for a
    ``from_json`` classmethod. Union of any kind of complex typing will not
    work.

    Second, due to the first caveat, this function will not return an instance
    of `cls`, but a dict mapping field name from field values. Further
    deserialization may be performed before constructing an instance with
    ``cls.__init__(**fields)``, where fields is the return value of this function.

    This is intended as a helper function to implement a ``from_json``
    classmethod on attr-decorated classes.

    Arguments:
        cls: class to deserialize against. Must be an att-decorated class
        obj: json object to deserialize
        ignore: fields of ``cls`` to ignore. The function behaves exactly as if
            ``cls`` did not have those fields. In particular, `unjsonize` will
            raise an error if the fields are found in ``obj``.

    Returns:
        a dict mapping fields name from deserialized field values.

    Raises:

    """
    attr.resolve_types(cls)
    expected_fields = {
        name: field
        for name, field in attr.fields_dict(cls).items()
        if name not in ignore
    }
    required_fields = {
        n: f for n, f in expected_fields.items() if f.default is not attr.NOTHING
    }

    if not obj.keys() <= expected_fields.keys():
        raise ValueError(
            f"json object has invalid fields not found in {cls.__name__}: "
            + ", ".join(obj.keys() - expected_fields.keys())
        )
    if not required_fields.keys() <= obj.keys():
        raise ValueError(
            f"json object is missing required fields from {cls.__name__}: "
            + ", ".join(required_fields.keys() - obj.keys())
        )

    fields = {}
    for name, field in expected_fields.items():
        if name in obj:
            if isinstance(field.type, type) and hasattr(field.type, "from_json"):
                fields[name] = field.type.from_json(obj[name])  # type: ignore
            else:
                fields[name] = obj[name]

    return fields
