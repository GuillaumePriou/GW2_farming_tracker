from __future__ import annotations

import functools
import inspect
import traceback
import types
import typing
from collections import abc
from typing import Any, Callable, Generic, Iterable, TypeAlias, TypeVar, overload

import attr
import trio

T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")
Cls = TypeVar("Cls", bound=type)

JsonValue: TypeAlias = None | bool | int | float | str
JsonArray: TypeAlias = list["AnyJson"]
JsonObject: TypeAlias = dict[str, "AnyJson"]
AnyJson: TypeAlias = JsonValue | JsonArray | JsonObject

AttrClass: TypeAlias = type


class SimpleNamespace(Generic[T]):
    """
    Typed version of `types.SimpleNamespace`
    """

    def __init__(self, /, **kwargs: T):
        self.__dict__.update(kwargs)

    def __repr__(self):
        items = (f"{k}={v!r}" for k, v in self.__dict__.items())
        return "{}({})".format(type(self).__name__, ", ".join(items))

    def __eq__(self, other):
        if isinstance(self, SimpleNamespace) and isinstance(other, SimpleNamespace):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __getattribute__(self, __name: str) -> T:
        return super().__getattribute__(__name)

    def __setattr__(self, __name: str, __value: T) -> None:
        return super().__setattr__(__name, __value)


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


def err_str(err: BaseException) -> str:
    return f"{err.__class__.__name__}: {err!s}"


def err_traceback(err: BaseException) -> str:
    return "".join(traceback.format_exception(err))  # type: ignore


def unjsonize(
    cls: AttrClass, obj: JsonObject, *, ignore: abc.Container[str] = ()
) -> dict[str, Any]:
    """
    Deserialize an attr class from json format.

    Deserialize an attr class from the json format. This is the inverse
    operation from `jsonize`, with the following caveats:
        - type annotations are used to infer the presence of a ``from_json``
          method on the field's type. Only extremely simple type annotations
          are properly tested:
            - Simple classes
            - Union of exactly None and a simple classe (i.e. ``Optional[]``)
        - due to the above, this function returns the (partially) deserialized
          fields rather than an instance. The caller can then further convert
          fields whose type annotation is too complex for this function.

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
            tp = field.type
            orig = typing.get_origin(field.type)
            args = typing.get_args(field.type)
            # black formatter doesn't support match/case yet
            # match field.type, orig, args:
            #    case (
            #        (tp, _, _)
            #        |  (_, typing.Union | types.UnionType, [None, tp] | [tp, None])
            #    ) if isinstance(tp, type) and hasattr(tp, "from_json"):
            #        # simple class type annotations
            #        fields[name] = tp.from_json(obj[name]) # type: ignore
            if orig is typing.Union or orig is types.UnionType:
                if len(args) == 2 and None in args:
                    # extract the type from the Optional[tp] or Union[None, tp] or None | tp
                    tp = next(filter(None, args))
            if isinstance(tp, type) and hasattr(tp, "from_json"):
                fields[name] = tp.from_json(obj[name])  # type: ignore
            else:
                fields[name] = obj[name]

    return fields


@overload
async def gather(task: abc.Awaitable[T]) -> tuple[T]:
    ...


@overload
async def gather(t1: abc.Awaitable[T], t2: abc.Awaitable[U]) -> tuple[T, U]:
    ...


@overload
async def gather(
    t1: abc.Awaitable[T], t2: abc.Awaitable[U], t3: abc.Awaitable[V]
) -> tuple[T, U, V]:
    ...


@overload
async def gather(*tasks: abc.Awaitable[T]) -> tuple[T, ...]:
    ...


async def gather(*tasks):
    async def collect(results: list, index: int, task: abc.Awaitable):
        results[index] = await task

    results = [Any] * len(tasks)
    async with trio.open_nursery() as nursery:
        for index, task in enumerate(tasks):
            nursery.start_soon(collect, results, index, task)

    return tuple(results)
