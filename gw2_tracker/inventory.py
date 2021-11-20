# -*- coding: utf-8 -*-
"""
Package defining a GW2 inventory and how to process it.

Main features : 
    - Fetch account inventory from GW2 API
    - Load/Save inventory from/to a file (includes metadata : date, API key)

@author: Krashnark
"""
from __future__ import annotations

import json
import threading
import types
import typing
from collections import abc
from attr import frozen, field
from pathlib import Path
from typing import IO, Any, Mapping
import attr

import pendulum
from pendulum.datetime import DateTime

@frozen
class Inventory(abc.Mapping[str, int]):
    """
    Immutable mapping from string ID to non-zero amounts

    Includes utility methods such as comparisons, serialization
    and addition/substraction. Inventory object can be compared to int
    and to themselves. Comparison to int is equivalent to comparing
    all values to the int. Comparison to another inventory compares the keys
    as sets and the values one-by-one. This is performed by checking the
    difference of the compared set to 0.
    """

    content: Mapping[str, int] = field(factory=dict)

    @classmethod
    def from_file(cls, file: str | Path | IO[bytes] | IO[str]) -> Inventory:
        """
        Deserialize an `Inventory` from a file

        Arguments:
            file: file name, `Path` or opened file to read from

        Returns:
            deserialized `Inventory` object

        Raises:
            ValueError: the file is not in the correct format
        """
        if hasattr(file, "read"):
            file = typing.cast(IO, file)
            content = json.loads(file.read())
        else:
            file = typing.cast(str | Path, file)
            with Path(file).open("rt", encoding="utf-8") as f:
                content = json.load(f)
        return cls.from_json(content)

    @classmethod
    def from_json(cls, obj: Any) -> Inventory:
        """
        Deserialize an `Inventory` from an already loaded JSON

        Argument:
            obj: json object to deserialize

        Returns:
            deserialized `Inventory` object

        Raises:
            ValueError: the json object is not in the correct format
        """
        if not (
            isinstance(obj, dict)
            and all(isinstance(k, str) and isinstance(v, int) for k, v in obj.items())
        ):
            raise ValueError(f"json should be a dict[str, int], got {obj}")
        return cls(obj)

    def __post_init__(self):
        # make content immutable
        self.__dict__["content"] = types.MappingProxyType(
            {k: v for k, v in self.content.items() if v}
        )

    def __getitem__(self, key: str) -> int:
        return self.content[key]

    def __len__(self) -> int:
        return len(self.content)

    def __iter__(self) -> abc.Iterator[str]:
        return iter(self.content)

    def __add__(self, other: Inventory) -> Inventory:
        if isinstance(other, Inventory):
            return Inventory(
                {
                    k: self.get(k, 0) + other.get(k, 0)
                    for k in self.keys() | other.keys()
                }
            )
        return NotImplemented

    def __sub__(self, other: Inventory) -> Inventory:
        if isinstance(other, Inventory):
            return Inventory(
                {
                    k: self.get(k, 0) - other.get(k, 0)
                    for k in self.keys() | other.keys()
                }
            )
        return NotImplemented

    def __lt__(self, other: int | Inventory) -> bool:
        if isinstance(other, int):
            return all(v < other for v in self.values())
        elif isinstance(other, Inventory):
            diff = other - self
            return bool(diff) and (diff > 0)
        return NotImplemented

    def __le__(self, other: int | Inventory) -> bool:
        if isinstance(other, int):
            return all(v <= other for v in self.values())
        elif isinstance(other, Inventory):
            return (other - self) >= 0
        return NotImplemented

    def __ge__(self, other: int | Inventory) -> bool:
        if isinstance(other, int):
            return all(v >= other for v in self.values())
        elif isinstance(other, Inventory):
            return (self - other) >= 0
        return NotImplemented

    def __gt__(self, other: int | Inventory) -> bool:
        if isinstance(other, int):
            return all(v > other for v in self.values())
        elif isinstance(other, Inventory):
            diff = self - other
            return bool(diff) and (diff > 0)

    def to_json(self) -> dict[str, int]:
        """Serialize the instance to json format"""
        return dict(self.content)

    def to_file(self, file: str | Path | IO[str], indent=4, sort_keys=True, **kwargs):
        """Serialize the instance to json format and write to the file

        Arguments:
            file: file name, `Path` or `IO` object to write to
            kwargs: additional keywords argument to pass to `json.dump`
        """
        kwargs = kwargs | dict(indent=indent, sort_keys=sort_keys)
        content = self.to_json()
        if hasattr(file, "write"):
            file = typing.cast(IO[str], file)
            json.dump(content, file, **kwargs)
        else:
            file = typing.cast(str | Path, file)
            with Path(file).open("wt", encoding="utf-8") as fp:
                json.dump(content, fp, **kwargs)


@frozen
class Snapshot:
    api_key: str
    inventory: Inventory
    datetime: DateTime = field(factory=pendulum.now)
    name: None | str = None

    @classmethod
    def from_file(cls, file: str | Path | IO[bytes] | IO[str]) -> Snapshot:
        """
        Deserialize a `Snapshot` from a file

        Arguments:
            file: file name, `Path` or opened file to read from

        Returns:
            deserialized object

        Raises:
            ValueError: the file is not in the correct format
        """
        if hasattr(file, "read"):
            file = typing.cast(IO, file)
            content = json.loads(file.read())
        else:
            file = typing.cast(str | Path, file)
            with Path(file).open("rt", encoding="utf-8") as f:
                content = json.load(f)
        return cls.from_json(content)

    @classmethod
    def from_json(cls, obj: Any) -> Snapshot:
        """
        Deserialize an `Inventory` from an already loaded JSON

        Argument:
            obj: json object to deserialize

        Returns:
            deserialized object

        Raises:
            ValueError: the json object is not in the correct format
        """
        if not isinstance(obj, dict):
            raise ValueError(f"expected a JSON object, got {obj}")
        else:
            expected_keys = attr.fields_dict(cls).keys()
            required_keys = {f.name for f in attr.fields(cls) if f.default is not attr.NOTHING}
            if not obj.keys() <= expected_keys:
                raise ValueError("JSON object has spurious keys " + ", ".join(obj.keys() - expected_keys))
            if not required_keys <= obj.keys():
                raise ValueError("JSON object is missing required keys " + ", ".join(required_keys - obj.keys()))
            
            api_key = str(obj["api_key"])
            inventory = Inventory.from_json(obj["inventory"])
            datetime = pendulum.parser.parse(obj["datetime"])
            if not isinstance(datetime, DateTime):
                raise ValueError(f"Excepted DateTime object at key 'datetime', got {type(datetime).__name__} object {datetime}")
            name = obj.get("name")

            return Snapshot(api_key, inventory, datetime, name)

    def to_json(self) -> dict[str, Any]:
        """Serialize the instance to JSON"""
        return {
            "api_key": self.api_key,
            "inventory": self.inventory.to_json(),
            "datetime": self.datetime.isoformat(),
            "name": self.name
        }
    
    def to_file(self, file: str | Path | IO[str], indent=4, sort_keys=True, **kwargs):
        """Serialize the instance to json format and write to the file

        Arguments:
            file: file name, `Path` or `IO` object to write to
            kwargs: additional keywords argument to pass to `json.dump`
        """
        kwargs = kwargs | dict(indent=indent, sort_keys=sort_keys)
        content = self.to_json()
        if hasattr(file, "write"):
            file = typing.cast(IO[str], file)
            json.dump(content, file, **kwargs)
        else:
            file = typing.cast(str | Path, file)
            with Path(file).open("wt", encoding="utf-8") as fp:
                json.dump(content, fp, **kwargs)