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

import enum
import functools
import json
import types
import typing
from collections import abc
from pathlib import Path
from typing import IO, Any, ClassVar, Iterable, Mapping, NewType, TypeAlias, TypedDict

import attr
import pendulum
from pendulum.datetime import DateTime

from gw2_tracker import protocols, utils

APIKey: TypeAlias = NewType("APIKey", str)
ItemID: TypeAlias = NewType("ItemID", str)


class ItemData(TypedDict):
    """
    Data returned by the GW2 API on an item

    Attributes:
        id: numeric ID of the item
        chat_link: special marker to link the item in chat in-game
        icon: url to the icon of the item
        type: type of item
        rarity
        level:
        vendor_value: values of the item when directly sold to merchant
        flags:
        game_types: game types in which the item is available
        restrictions: which character can use this item (e.g. cultural armor is
            restricted to character of the culture)
    """

    id: int
    chat_link: str
    name: str
    icon: str
    type: str
    rarity: str
    level: int
    vendor_value: int
    flags: list[str]
    game_types: list[str]
    restrictions: list[str]


@attr.frozen
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

    content: Mapping[str, int] = attr.field(factory=dict)

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

    def to_file(
        self, file: str | Path | IO[str], indent=4, sort_keys=True, **kwargs
    ) -> None:
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


@attr.frozen
class Snapshot:
    """
    Immutable representation of an account state at a given datetime.
    """

    key: APIKey
    inventory: Inventory
    wallet: Inventory
    datetime: DateTime = attr.field(factory=pendulum.now)
    name: None | str = None

    @classmethod
    def from_file(cls, file: str | Path | IO[bytes] | IO[str]) -> Snapshot:
        """
        Deserialize an object from a file

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
    def from_json(cls, obj: utils.JsonObject) -> Snapshot:
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
        return cls(**fields)

    def to_json(self) -> utils.JsonObject:
        """Serialize the instance to JSON"""
        fields = utils.jsonize(self)
        fields["datetime"] = fields["datetime"].isoformat()
        return fields

    def to_file(
        self, file: str | Path | IO[str], indent=4, sort_keys=True, **kwargs
    ) -> None:
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


@attr.frozen
class ItemDetail:
    """
    Data kept in reports

    Attributes:
        id: item ID
        name: full name of the item
        vendor_value: price of the item when sell to a merchant (0 if cannot
            be sold)
        highest_buy: highest black lion buy order for that item at the time of
            creation of the instance
        lowest_sell: lowest black lion sell order for that item at the time of
            creation of the instance
    """

    BLACK_LION_FEE: ClassVar[float] = 0.15

    id: str
    name: str
    vendor_value: int
    highest_buy: None | int
    lowest_sell: None | int
    icon_path: None | Path = None

    @classmethod
    def from_file(cls, file: str | Path | IO[bytes] | IO[str]) -> ItemDetail:
        """
        Deserialize a `ItemDetail` object from a file

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
    def from_json(cls, obj: utils.JsonObject) -> ItemDetail:
        """
        Deserialize an object from an already loaded JSON

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
        return cls(**fields)

    def to_json(self) -> utils.JsonObject:
        """Serialize the instance to JSON"""
        return utils.jsonize(self)

    def to_file(
        self, file: str | Path | IO[str], indent=4, sort_keys=True, **kwargs
    ) -> None:
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

    @functools.cached_property
    def value_black_lion_fast(self) -> None | int:
        """Value of the item when selling it instantly to the black lion"""
        if self.highest_buy is not None:
            return int((1 - self.BLACK_LION_FEE) * self.highest_buy)

    @functools.cached_property
    def value_fast(self) -> int:
        """Highest value when selling the item immediatly to black lion of vendor"""
        return max(self.value_black_lion_fast or 0, self.vendor_value)

    @functools.cached_property
    def value_black_lion_slow(self) -> None | int:
        """Value of the item when placing a sell order and waiting"""
        if self.lowest_sell is not None:
            return int((1 - self.BLACK_LION_FEE) * self.lowest_sell)
        elif self.highest_buy is not None:
            # fall back on the buy order and a fast sell
            return int((1 - self.BLACK_LION_FEE) * self.highest_buy)

    @functools.cached_property
    def value_slow(self) -> int:
        """
        Highest value of the item when placing a sell order and waiting or
        selling to vendor
        """
        return max(self.value_black_lion_slow or 0, self.vendor_value)

    @functools.cached_property
    def value_black_lion(self) -> None | int:
        """Highest possible value at the black lion, or None if no offers"""
        return self.value_black_lion_slow

    @functools.cached_property
    def value(self) -> int:
        """Highest possible value at the black lion or vendor"""
        return self.value_slow


# functools.cached_properties uses __dict__, cannot use slots
@attr.frozen(slots=False)
class Report:
    """
    Stores a computed gain report

    Attributes:
        start_date: datetime of the starting snapshot
        end_date: datetime of the final snapshot
        inv_diff: difference between starting and final inventory
        wallet_diff: difference between starting and final wallet
    """

    _DATETIME_FIELDS: ClassVar[Iterable[str]] = ("start_date", "end_date")
    _COIN_ID: ClassVar[str] = "1"

    start_date: DateTime
    end_date: DateTime
    inv_diff: Inventory
    wallet_diff: Inventory
    item_details: Mapping[str, ItemDetail]

    def __attrs_post_init__(self):
        if not (self.inv_diff.keys() <= self.item_details.keys()):
            raise ValueError(
                "no item details for ids: "
                + ", ".join(self.inv_diff.keys() - self.item_details.keys())
            )

    @classmethod
    def from_file(cls, file: str | Path | IO[bytes] | IO[str]) -> Report:
        """
        Deserialize a `ItemDetail` object from a file

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
    def from_json(cls, obj: utils.JsonObject) -> Report:
        """
        Deserialize an object from an already loaded JSON

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
        for dt_field in cls._DATETIME_FIELDS:
            fields[dt_field] = DateTime, pendulum.parser.parse(fields[dt_field])
        return cls(**fields)

    def to_json(self) -> utils.JsonObject:
        """Serialize the instance to JSON"""
        fields = utils.jsonize(self)
        for dt_field in self._DATETIME_FIELDS:
            fields[dt_field] = fields[dt_field].isoformat()
        return fields

    def to_file(
        self, file: str | Path | IO[str], indent=4, sort_keys=True, **kwargs
    ) -> None:
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

    @property
    def coins(self) -> int:
        """
        Number of coins gained or lost during the period
        """
        # May not be there is the diff is 0, inventory strips out zeros
        return self.wallet_diff.get(self._COIN_ID, 0)

    @functools.cached_property
    def item_gains(self) -> int:
        """gains from item changes only"""
        return sum(
            count * self.item_details[id_].value for id_, count in self.inv_diff.items()
        )

    @property
    def total_gains(self) -> int:
        """Total gains in coins"""
        return self.coins + self.item_gains


@attr.mutable
class Cache:
    """
    Handles API data cached by the app
    """

    dirpath: Path = attr.field(converter=Path)
    item_data: dict[ItemID, ItemData] = attr.field(factory=dict)
    images: list[ItemID] = attr.field(factory=list)

    # @classmethod
    # def from_dir(cls, dirpath: Path) -> Cache:
    #    # TODO
    #
    #    pass


class States(enum.IntEnum):
    """
    States of the application repressenting the steps in the computation
    """

    STARTED = 0
    KEY = 1
    SNAP_START = 2
    SNAP_END = 3
    REPORT = 4

    @classmethod
    def from_json(cls, value) -> States:
        return cls(value)

    def to_json(self) -> int:
        return self._value_


@attr.mutable
class Model:
    """
    Complete state of the application
    """

    filepath: Path = attr.field(converter=Path)
    state: States = States.STARTED
    current_key: None | APIKey = None
    start_snapshot: None | Snapshot = None
    end_snapshot: None | Snapshot = None
    report: None | Report = None

    @classmethod
    def from_file(cls, filepath: str | Path) -> Model:
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
        return Model(filepath=filepath, **fields)

    def to_json(self) -> utils.JsonObject:
        """Serialize an instance as JSON"""
        return utils.jsonize(self, ignore=["filepath"])

    def to_file(self, indent=4, sort_keys=True, **kwargs) -> None:
        """Serialize the instance to it's file"""
        with self.filepath.open("wt", encoding="utf-8") as file:
            json.dump(
                self.to_json(), file, indent=indent, sort_keys=sort_keys, **kwargs
            )

    async def save(self) -> None:
        """Asynchronously save this instance"""
        # TODO: make that IO async
        # is there an async version of json ?
        self.to_file()

    def set_key(self, key: APIKey, trio_guest: protocols.TrioGuestProto = None) -> None:
        """
        Set a new key as the current key. Key is assumed to be valid

        Arguments:
            key: key to set as the current key
            trio_guest: is not None, schedule an asynchronous save of the
                modified models with this object
        """
        self.state = States.KEY
        self.current_key = key

        if trio_guest is not None:
            copy = attr.evolve(self)
            trio_guest.start_soon(copy.save)

    def set_start_snapshot(
        self, snapshot: Snapshot, trio_guest: protocols.TrioGuestProto = None
    ) -> None:
        """
        Stores a snapshot as the start snapshot

        Arguments:
            snapshot: snaphost to set as the start snapshot
            trio_guest: is not None, schedule an asynchronous save of the
                modified models with this object
        """
        if self.state < States.KEY:
            raise ValueError("Cannot set starting snapshot without a key")

        if self.current_key != snapshot.key:
            raise ValueError(
                f"Current key {self.current_key} doesn't match snapshot key {snapshot.key}"
            )

        self.start_snapshot = snapshot
        self.state = States.SNAP_START

        if trio_guest is not None:
            copy = attr.evolve(self)
            trio_guest.start_soon(copy.save)

    def set_end_snapshot(
        self, snapshot: Snapshot, trio_guest: protocols.TrioGuestProto = None
    ) -> None:
        """
        Stores a snapshot as the after snapshot

        Arguments:
            snapshot: snapshot to set as the end snapshot
            trio_guest: is not None, schedule an asynchronous save of the
                modified models with this object
        """
        if self.state < States.SNAP_START:
            raise ValueError("Cannot set later snapshot without a starting snapshot")

        if self.current_key != snapshot.key:
            raise ValueError(
                f"Current key {self.current_key} doesn't match snapshot key {snapshot.key}"
            )

        self.end_snapshot = snapshot
        self.state = States.SNAP_END

        if trio_guest is not None:
            copy = attr.evolve(self)
            trio_guest.start_soon(copy.save)

    def set_report(
        self, report: Report, trio_guest: protocols.TrioGuestProto = None
    ) -> None:
        """Stores a report as the current report

        Arguments:
            report: report to store
            trio_guest: is not None, schedule an asynchronous save of the
                modified models with this object
        """
        if self.state < States.SNAP_END:
            raise ValueError("Cannot set report without an end snapshot")

        self.report = report
        self.state = States.REPORT

        if trio_guest is not None:
            copy = attr.evolve(self)
            trio_guest.start_soon(copy.save)

    # def get_inventory_and_compare_it(self):
    #     """
    #     Get full inventory of an account and put it in new/updated inventory.
    #     Then compare reference inventory with new inventory and build the report.
    #     """
    #     if self.applicationState in ("0 - started", "1 - got api key"):
    #         raise ValueError("Missing key or reference inventory !")
    #     self.newInventory.get_full_inventory(self.apiKey.keyValue)

    #     self.referenceInventory.save_to_file(
    #         "Application_data/end_inventory.txt", self.apiKey.keyValue
    #     )
    #     self.applicationState = "3 - got end inventory"
    #     self.report.compare_inventories(self.referenceInventory, self.newInventory)

    #     print(
    #         f"function get inventory & compare it : report content after comparison :"
    #     )
    #     print(f"   self.report.itemsDetail : {self.report.itemsDetail}")

    #     self.report.get_item_details()

    #     print(
    #         f"function get inventory & compare it : report content after getting details :"
    #     )
    #     print(f"   self.report.itemsDetail : {self.report.itemsDetail}")

    #     self.applicationState = "4 - got full report"

    #     # with open("debug/new_inventory.txt", 'w') as f:
    #     #     json.dump(self.newInventory.items, f, indent=3, ensure_ascii=False)


@attr.mutable
class _Model:
    """
    Save the application state
    """

    filepath: Path = attr.field(converter=Path)
    current_key: None | APIKey = None
    data: dict[APIKey, list[Snapshot]] = attr.field(factory=dict)

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
        return cls(filepath=filepath, **fields)

    def save(self, indent=4, sort_keys=True, **kwargs):
        """Save the model to the given file"""
        obj = utils.jsonize(self, ignore=["filepath"])
        with self.filepath.open("wt", encoding="utf-8") as file:
            json.dump(obj, file, indent=indent, sort_keys=sort_keys, **kwargs)
