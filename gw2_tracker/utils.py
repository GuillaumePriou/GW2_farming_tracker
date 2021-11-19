from __future__ import annotations

import functools
import inspect
from typing import Callable, Iterable, ParamSpec, Type, TypeVar, overload

Cls = TypeVar("Cls", bound=type)


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
