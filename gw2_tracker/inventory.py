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
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Mapping

import pendulum


@dataclass(frozen=True)
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

    content: Mapping[str, int] = field(default_factory=dict)

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


@dataclass
class Snapshot:
    api_key: str
    inventory: Inventory
    timestamp = field(default_factory=pendulum.now)
    name: None | str = None
