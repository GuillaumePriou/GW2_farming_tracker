# -*- coding: utf-8 -*-
"""
Model layer of GW2 tool to evaluate gold earnings.

Main features :
    - set API key (Model.apiKey)
    - get inventory and define it as reference
    - get inventory and compare it to the reference
    - generates full report for user

@author: Krashnark
"""

from __future__ import annotations

import json
import os.path
import types
import typing
from collections import abc
from pathlib import Path
from typing import IO, Any, Mapping, NewType, TypeAlias

import attr
import pendulum
from attr import field, frozen, mutable
from pendulum.datetime import DateTime

from gw2_tracker import utils

APIKey: TypeAlias = NewType("APIKey", str)


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

    def __attrs_post_init__(self):
        # make content immutable
        object.__setattr__(
            self,
            "content",
            types.MappingProxyType({k: v for k, v in self.content.items() if v}),
        )

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


@frozen
class Snapshot:
    key: APIKey
    inventory: Inventory
    wallet: Inventory
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

        fields = utils.unjsonize(cls, obj)
        fields["key"] = APIKey(fields["key"])
        fields["datetime"] = DateTime, pendulum.parser.parse(fields["datetime"])
        return Snapshot(**fields)

    def to_json(self) -> utils.JsonObject:
        """Serialize the instance to JSON"""
        fields = utils.jsonize(self)
        fields["datetime"] = fields["datetime"].isoformat()
        return fields

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


@mutable
class _Model:
    """
    Save the application state
    """

    filepath: Path = field(converter=Path)
    current_key: None | APIKey = None
    data: dict[APIKey, list[Snapshot]] = field(factory=dict)

    @classmethod
    def from_file(cls, filepath: str | Path) -> _Model:
        """
        Deserialize a model from a file and make the model save itself
        to this file
        """
        filepath = Path(filepath)

        with filepath.open("rt", encoding="utf-8") as file:
            obj = json.load(file)

        if not isinstance(obj, dict):
            raise ValueError(f"{filepath} does not contain a json object")

        fields = utils.unjsonize(cls, obj, ignore=["filepath"])
        return _Model(filepath=filepath, **fields)

    def save(self):
        """Save the model to the given file"""
        obj = utils.jsonize(self, ignore=["filepath"])
        with self.filepath.open("wt", encoding="utf-8") as file:
            json.dump(obj, file)


class Model:
    def __init__(self, api_key=""):
        """
        Model initialization.

        self.applicationState possible values :
            - "0 - started"
            - "1 - got api key"
            - "2 - got start inventory"
            - "3 - got end inventory"
            - "4 - got full report"
        """
        self.applicationState = "0 - started"
        self.apiKey = (
            gw2_api.APIKey()
        )  # Declare API key, try to load a previously saved API key
        self.referenceInventory = Inventory()
        self.newInventory = Inventory()
        self.report = report.Report()

        if self.apiKey.keyValue != "":
            self.applicationState = "1 - got api key"

        if self.applicationState == "1 - got api key":
            # Try to load saved reference inventory
            if os.path.isfile("Application_data/start_inventory.txt"):
                self.referenceInventory.load_from_file(
                    "Application_data/start_inventory.txt", self.apiKey.keyValue
                )
                self.applicationState = "2 - got start inventory"
            else:
                print("Could not find saved and valid reference inventory.")

        # This loading do not make sense without loading the full report
        # if self.applicationState == "2 - got start inventory" :
        #     # try to load target inventory
        #     try:
        #         self.referenceInventory.load_from_file("Application_data/end_inventory.txt", self.apiKey)
        #         self.applicationState = "3 - got end inventory"
        #     except ValueError as error :
        #         print ("Could not find saved and valid reference inventory.")
        #         print (error)

        # Maybe will implement load function for report.
        # Maybe...

    def set_new_key(self, new_key):
        """User set a new key. Let's validate it and save it."""
        try:
            self.apiKey.keyValue = new_key
            self.applicationState = "1 - got api key"
        except:
            pass

    def set_reference_inventory(self):
        """Get full inventory of an account and put it in reference inventory"""
        if self.applicationState == "0 - started":
            raise ValueError("Key was not yet defined !")

        self.referenceInventory.get_full_inventory(self.apiKey.keyValue)

        self.referenceInventory.save_to_file(
            "Application_data/start_inventory.txt", self.apiKey.keyValue
        )

        self.applicationState = "2 - got start inventory"

        # with open("debug/reference_inventory.txt", 'w') as f:
        #     json.dump(self.referenceInventory.items, f, indent=3, ensure_ascii=False)

    def get_inventory_and_compare_it(self):
        """
        Get full inventory of an account and put it in new/updated inventory.
        Then compare reference inventory with new inventory and build the report.
        """
        if self.applicationState in ("0 - started", "1 - got api key"):
            raise ValueError("Missing key or reference inventory !")
        self.newInventory.get_full_inventory(self.apiKey.keyValue)

        self.referenceInventory.save_to_file(
            "Application_data/end_inventory.txt", self.apiKey.keyValue
        )
        self.applicationState = "3 - got end inventory"
        self.report.compare_inventories(self.referenceInventory, self.newInventory)

        print(
            f"function get inventory & compare it : report content after comparison :"
        )
        print(f"   self.report.itemsDetail : {self.report.itemsDetail}")

        self.report.get_item_details()

        print(
            f"function get inventory & compare it : report content after getting details :"
        )
        print(f"   self.report.itemsDetail : {self.report.itemsDetail}")

        self.applicationState = "4 - got full report"

        # with open("debug/new_inventory.txt", 'w') as f:
        #     json.dump(self.newInventory.items, f, indent=3, ensure_ascii=False)
