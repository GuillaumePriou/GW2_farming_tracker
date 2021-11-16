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
from collections import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Mapping

from gw2_tracker import gw2_api


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
    def from_file(cls, file: str | Path | IO[bytes | str]) -> Inventory:
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
            content = json.loads(file.read())
        else:
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
        return Inventory(obj)

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
            return diff and diff > 0
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
            return diff and diff > 0

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
            json.dump(content, file, **kwargs)
        else:
            with Path(file).open("wt", encoding="utf-8") as fp:
                json.dump(content, fp, **kwargs)

    ## Old API - Remove

    @classmethod
    def load_from_file(cls, source_file, api_key_to_match):
        """Open source_file and load the inventory stored there into items attributes.

        Arguments :
            - source_file : location where to find the saved inventory
            - api_key_to_match : API key the application is currently using.
            If the saved inventory used a different key, loading is cancelled.
        """
        with open(source_file, "r") as f:
            print("Found saved reference inventory.")
            fileContent = json.load(f)
            if api_key_to_match == fileContent["API key"]:
                # Extract key and save it separately
                del fileContent["API key"]
                print("Loaded saved reference inventory.")
                return cls(items=fileContent)
            else:
                print(
                    "API key from reference inventory does not match current API key. Discarded saved inventory."
                )
                raise ValueError(
                    f'Loading cancelled : API keys do not match. \
                                  Key from saved inventory is {fileContent["API key"]} \
                                  while expected key is {api_key_to_match}'
                )

    def save_to_file(self, target_file, api_key):
        """Save the inventory to a file.

        Arguments :
            - filename in which to save the inventory.
            - key used to get the data

        Note :
            - if file already exist, it will be overwritten.
            - The API key will saved as an item amongst the other.
        """
        with open(target_file, "w") as outfile:
            tmp_dict = self.items.copy()
            tmp_dict["API key"] = api_key

            json.dump(tmp_dict, outfile, indent=3, ensure_ascii=False)
            print("Saved start inventory into file.")

    def _get_item_data_from_slot(self, inventory_slot):
        """Internal function. Parse the slot data returned by the API

        Argument : the dict data describing the object contained in a slot
        Output : a 2 elements tuple (item id, item count)
        If the item has a 'charge' attribute, this value will replace the 'count'
        attribute in the output. Items with charges are not stackable anyway.

        /!\ This function assumes the input is not None' i.e slot is non-empty.
        """
        item_id = inventory_slot["id"]

        if "charges" in inventory_slot:  # We care about charges for consumable items
            item_count = inventory_slot["charges"]
        elif "count" in inventory_slot:
            item_count = inventory_slot["count"]
        elif "value" in inventory_slot:
            item_count = inventory_slot[
                "value"
            ]  # Wallet currencies use 'value' instead of 'count' attribute
        else:
            raise ValueError("Error while parsing data coming from an inventory slot.")

        return (item_id, item_count)

    def _get_account_generic_data(
        self, api_url, api_key, ptr_lock, ptr_unaggregatedItemResults
    ):
        """Internal function. Get the requested account data via API.

        Arguments :
            - api_url: valid GW2 API url
            - api_key : key with appropriate authorization level to access the data (provided by model object)
            - ptr_unaggregatedItemResults : a variable to fill with the calculation result
            - ptr_lock : lock object to allow several thread to fill ptr_unaggregatedItemResults
        Output :
            list of objects where object contain the following : id, count (or charge when applicable)
            Output is written directly in parent function variable with a lock constraint

        Typically used to get shared inventory, bank and wallet.
        """

        api_output = gw2_api.GW2_API_handler(api_url, api_key)

        # print(f'Output of call to {api_url} : {api_output}')
        """file = "debug/account_generic_data.txt"
        with open(file, 'a') as f:
            json.dump({"api_url" : api_url}, f, indent=3, ensure_ascii=False)
            json.dump(api_output, f, indent=3, ensure_ascii=False)
        """
        content = list()

        if api_output != "":
            for slot in api_output:  # Process each slot in shared inventory
                if slot != None:
                    content.append(self._get_item_data_from_slot(slot))

        with ptr_lock:
            ptr_unaggregatedItemResults += content

    def _get_inventory_of_single_character(
        self, character_name, api_key, ptr_lock, ptr_unaggregatedItemResults
    ):
        """Internal function. Retrieve inventory of a single character of an account via API.

        Arguments :
            - character name : the character for which the function should retrieve the inventory
            - api key : key with appropriate authorization level to access the data (provided by model object)
            - ptr_unaggregatedItemResults : a variable to fill with the calculation result
            - ptr_lock : lock object to allow several thread to fill ptr_unaggregatedItemResults
        Output :
            list of objects where object contain the following : id, count (or charge when applicable)
            Output is written directly in parent function variable with a lock constraint
        """
        # Build API URL
        character_inventory_url = "https://api.guildwars2.com/v2/characters/"
        character_inventory_url += character_name.replace(
            " ", "%20"
        )  # Percent encoding required by GW2 API
        character_inventory_url += "/inventory"

        # Get API answer
        character_inventory = gw2_api.GW2_API_handler(character_inventory_url, api_key)

        # Parse API answer : inventory bag per bag
        character_items = []

        for bag in character_inventory["bags"]:
            if bag != None:  # None means bag is empty
                for slot in bag[
                    "inventory"
                ]:  # items are stored in an inventory element
                    if slot != None:  # empty slots are 'null' string instead of dict
                        character_items.append(self._get_item_data_from_slot(slot))

        """file = "debug/character_inventories.txt"
        with open(file, 'a') as f:
            json.dump(character_inventory, f, indent=3, ensure_ascii=False)
        """

        # save results
        with ptr_lock:
            ptr_unaggregatedItemResults += character_items

    def _get_materials_bank(self, api_key, ptr_lock, ptr_unaggregatedItemResults):
        """Internal function. Retrieve material inventory of an account via API.

        Argument :
            - api key : key with appropriate authorization level to access the data (provided by model object)
            - ptr_unaggregatedItemResults : a variable to fill with the calculation result
            - ptr_lock : lock object to allow several thread to fill ptr_unaggregatedItemResults

        Output : list of objects where object contain the following : id, count (or charge when applicable)

        ? Maybe this function would be replaced by a call to get_account_generic_data
        """

        materials = gw2_api.GW2_API_handler(
            "https://api.guildwars2.com/v2/account/materials", api_key
        )

        """with open('debug/materials_in_bank.txt', 'w') as f:
            json.dump(materials, f, indent=3, ensure_ascii=False)
        """

        parsed_materials = list()

        for item in materials:
            if (
                item["count"] > 0
            ):  # This condition is the only reason this funtion exists separately
                parsed_materials.append((item["id"], item["count"]))

        with ptr_lock:
            ptr_unaggregatedItemResults += parsed_materials

    def get_full_inventory(self, api_key):
        """Get list of player owned items from various sources :
        - banks (items and crafting materials)
        - inventories (shared and characters specific)
        Input : a valid api key for player account (provided by model object)
        Output : dictionnary (key = item id, value = item count/charges)

        Note : wallet is handled separately. Not in this function.

        Note 2 : all API calls are made simultaneously.
        """

        # A raw concatenation/merge of items lists so one item can have several entries.
        unaggregatedItemResults = []

        lock = (
            threading.Lock()
        )  # to make sure that no thread collides when saving results.

        threads = []

        self.items = dict()  # reset inventory data

        print("Get full inventory")

        # Get shared inventory
        print("  Get shared inventory...")
        threads.append(
            threading.Thread(
                target=self._get_account_generic_data,
                args=(
                    "https://api.guildwars2.com/v2/account/inventory",
                    api_key,
                    lock,
                    unaggregatedItemResults,
                ),
            )
        )

        # Get materials bank content
        print("  Get materials in bank...")
        threads.append(
            threading.Thread(
                target=self._get_materials_bank,
                args=(api_key, lock, unaggregatedItemResults),
            )
        )

        # Get characters inventories
        print("  Get characters inventories...")
        characters_list = gw2_api.GW2_API_handler(
            "https://api.guildwars2.com/v2/characters/", api_key
        )
        for character in characters_list:
            threads.append(
                threading.Thread(
                    target=self._get_inventory_of_single_character,
                    args=(character, api_key, lock, unaggregatedItemResults),
                )
            )

        # Get bank content
        print("  Get bank vault content...")
        threads.append(
            threading.Thread(
                target=self._get_account_generic_data,
                args=(
                    "https://api.guildwars2.com/v2/account/bank",
                    api_key,
                    lock,
                    unaggregatedItemResults,
                ),
            )
        )

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Aggregate data into self.referenceInventory
        print("Full inventory retrieved. Aggregating raw data...")
        for item in unaggregatedItemResults:
            if item[0] in self.items:
                self.items[item[0]] += item[1]
            else:
                self.items[item[0]] = item[1]

        print("Data aggregated. Inventory fetch complete.")
