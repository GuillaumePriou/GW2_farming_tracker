# -*- coding: utf-8 -*-
"""
Simple package containing just a function to call the GW2 API.

That is all. Dependency : requests library.

@author: Krashnark

Simple package for defining an API key behavior

Main features :
    - Check API key validity (including permissions)
    - Save/load API key from a file

@author: Krashnark
"""
import asyncio
from typing import Any, Final, NewType, TypeAlias, TypedDict, TypeVar

import asks
import requests
import trio
from attr import define

from gw2_tracker.inventory import APIKey, Inventory, Snapshot
from gw2_tracker.utils import autoformat

# Types aliases
T = TypeVar("T")
URL: TypeAlias = NewType("URL", str)
Token: TypeAlias = NewType("Token", object)

# Constants
URL_KEY_INFO: Final[URL] = URL("https://api.guildwars2.com/v2/tokeninfo")
URL_ACCOUNT_INVENTORY: Final[URL] = URL(
    "https://api.guildwars2.com/v2/account/inventory"
)
URL_BANK_INVENTORY: Final[URL] = URL("https://api.guildwars2.com/v2/account/bank")
URL_BANK_MATERIALS: Final[URL] = URL("https://api.guildwars2.com/v2/account/materials")
URL_CHARACTER_LIST: Final[URL] = URL("https://api.guildwars2.com/v2/characters/")
URL_CHARACTER_INVENTORY_TPL = (
    "https://api.guildwars2.com/v2/characters/{character}/inventory"
)

HTTP_OK: Final[int] = 200


class KeyPermissions(TypedDict):
    """
    Stores which permissions are available on an API key
    """

    wallet: bool
    inventories: bool
    characters: bool


class _SlotID(TypedDict):
    id: str


class Slot(_SlotID, TypedDict, total=False):
    charges: int
    count: int
    value: int


@define
class GW2APIError(Exception):
    """
    Base class for API related error
    """

    msg: str


@autoformat
@define
class APIKeyError(GW2APIError):
    """Base class for API Key-related errors"""

    key: APIKey


@autoformat
@define
class InvalidAPIKeyError(APIKeyError):
    msg: str = "Invalid API Key {key}"


@autoformat
@define
class KeyPermissionError(APIKeyError):
    """
    Insufficient permission on an API key
    """

    missing_perms: tuple[str, ...]
    msg: str = "API Key {key} does not have the required permissions {missing_perms}"


def get_headers(key: APIKey) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def get_key_permissions(key: APIKey) -> KeyPermissions | None:
    response = requests.get(URL_KEY_INFO, headers=get_headers(key))
    if response.status_code != HTTP_OK:
        return None
    else:
        content = response.json()
        permissions = content["permissions"]
        return KeyPermissions(
            wallet="wallet" in permissions,
            inventories="inventories" in permissions,
            characters="characters" in permissions,
        )


def validate_key(key: APIKey):
    perms = get_key_permissions(key)
    if perms is None:
        raise InvalidAPIKeyError(key=key)
    if not all(perms.values()):
        missing_perms = [k for k, v in perms.items() if not v]
        raise PermissionError(*missing_perms)


def is_key_valide(key: APIKey) -> bool:
    try:
        validate_key(key)
        return True
    except GW2APIError:
        return False


def unwrap_slot(slot: Slot) -> tuple[str, int]:
    """
    Unwrap a slots to a tuple, usable to init a dictionary

    If the slot is None, return ("", 0)
    """
    if slot:
        for k in ("charges", "count", "value"):
            if k in slot:
                count = slot[k]
                break
        else:
            raise ValueError(f"Invalid slot: {slot}")
    return slot["id"], count


async def call_api(session: asks.Session, url: URL, key: APIKey) -> Any:
    headers = get_headers(key)
    response = session.get(url, headers=headers)
    if response.status == HTTP_OK:
        return await response.json()
    else:
        raise GW2APIError(f"Could not reach {url}: {response}")


async def get_account_inventory(session: asks.Session, key: APIKey) -> Inventory:
    slots: list[Slot] = await call_api(session, URL_ACCOUNT_INVENTORY, key)
    return Inventory(dict(map(unwrap_slot, slots)))


async def get_bank_inventory(session: asks.Session, key: APIKey) -> Inventory:
    slots: list[Slot] = await call_api(session, URL_BANK_INVENTORY, key)
    return Inventory(dict(map(unwrap_slot, slots)))


async def get_bank_materials(session: asks.Session, key: APIKey) -> Inventory:
    slots: list[Slot] = await call_api(session, URL_BANK_MATERIALS, key)
    return Inventory(dict(map(unwrap_slot, slots)))


async def get_character_inventory(
    session: asks.Session, key: APIKey, character: str
) -> Inventory:
    # TODO: manually encode character name or aiohttp does it ?
    url = URL(URL_CHARACTER_INVENTORY_TPL.format(character=character))
    bags: list[list[Slot]] = await call_api(session, url, key)
    return sum(
        (Inventory(dict(map(unwrap_slot, bag))) for bag in bags if bag),
        start=Inventory(),
    )


async def get_characters_inventories(session: asks.Session, key: APIKey) -> Inventory:
    character_names: list[str] = await call_api(session, URL_CHARACTER_LIST, key)
    inventories = await asyncio.gather(
        *(
            get_character_inventory(session, key, character)
            for character in character_names
        )
    )
    return sum(inventories, start=Inventory())


async def get_aggregated_inventory(session: asks.Session, key: APIKey) -> Inventory:
    inventories = await asyncio.gather(
        *(
            coro(session, key)
            for coro in (
                get_account_inventory,
                get_bank_inventory,
                get_bank_materials,
                get_characters_inventories,
            )
        )
    )
    return sum(inventories, start=Inventory())


async def get_snapshot(session: asks.Session, key: APIKey):
    return Snapshot(key=key, inventory=await get_aggregated_inventory(session, key))


class GW2API:
    started: bool = False
    nursery: trio.Nursery
    session: asks.Session

    async def main(self):
        """
        Main trio routine to call from an host
        """
        self.session = asks.Session(connections=20)
        async with trio.open_nursery() as nursery:
            self.nursery = nursery
            self.started = True
            await trio.sleep_forever()

    def make_snapshot(self, controller, key: APIKey):
        if not self.started:
            raise RuntimeError(f"{self} is not started")
        self.nursery.start_soon(self._make_snapshot, controller, key)

    async def _make_snapshot(self, controller, key: APIKey):
        snapshot = await get_snapshot(self.session, key)
        controller.notify_new_snapshot(key, snapshot)


def GW2_API_handler(url, api_key=""):
    """A function to manage calls to GW2 API.
    Inputs:
        - URL
        - API key (optional, default = "")
    Output if successful : dict containing response content (response.json())
    Output if failure : empty string
    """
    headers = {"Authorization": "Bearer {}".format(api_key)}
    response = requests.get(url, headers=headers, timeout=15)

    if response.status_code == 200:
        return response.json()
    else:
        return ""
        # raise ValueError(f'Invalid request at {url} for key {api_key} : {response.status_code}')
