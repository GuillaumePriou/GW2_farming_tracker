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
from collections import abc
from pathlib import Path
from typing import Any, Final, NewType, TypeAlias, TypedDict, TypeVar

import asks
import attr
import requests
import trio
import yarl

from gw2_tracker import models, utils

# Types aliases
T = TypeVar("T")
Token: TypeAlias = NewType("Token", object)

# Constants
_URLS: Final[utils.SimpleNamespace[yarl.URL]] = utils.SimpleNamespace(
    BASE=(base := yarl.URL("https://api.guildwars2.com/v2")),
    KEY_INFO=base / "tokeninfo",
    ACCOUNT_INVENTORY=base / "account/inventory",
    ACCOUNT_WALLET=base / "account/wallet",
    BANK_INVENTORY=base / "account/bank",
    BANK_MATERIALS=base / "account/materials",
    CHARACTER_LIST=base / "characters",
    CHARACTER_INVENTORY=base / "characters/{character}/inventory",
    ITEM_PRICES=base / "commerce/prices",
    ITEM_DATA=base / "items",
)

_HTTP_OK: Final[int] = 200
_FLAG_NO_SELL: Final[str] = "NoSell"


class KeyPermissions(TypedDict):
    """
    Stores which permissions are available on an API key
    """

    wallet: bool
    inventories: bool
    characters: bool


class _SlotID(TypedDict):
    id: str


class _Slot(_SlotID, TypedDict, total=False):
    charges: int
    count: int
    value: int


class _Listing(TypedDict):
    unit_price: int
    quantity: int


class _ItemPrices(TypedDict):
    id: int
    whitelisted: bool
    buys: _Listing
    sells: _Listing


class _ItemData(TypedDict):
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


@attr.define
class GW2APIError(Exception):
    """
    Base class for API related error
    """

    msg: str


@utils.autoformat
@attr.define
class APIKeyError(GW2APIError):
    """Base class for API Key-related errors"""

    key: models.APIKey


@utils.autoformat
@attr.define
class InvalidAPIKeyError(APIKeyError):
    msg: str = "Invalid API Key {key}"


@utils.autoformat
@attr.define
class KeyPermissionError(APIKeyError):
    """
    Insufficient permission on an API key
    """

    missing_perms: tuple[str, ...]
    msg: str = "API Key {key} does not have the required permissions {missing_perms}"


def get_headers(key: models.APIKey) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def get_key_permissions(key: models.APIKey) -> KeyPermissions | None:
    response = requests.get(str(_URLS.KEY_INFO), headers=get_headers(key))
    if response.status_code != _HTTP_OK:
        return None
    else:
        content = response.json()
        permissions = content["permissions"]
        return KeyPermissions(
            wallet="wallet" in permissions,
            inventories="inventories" in permissions,
            characters="characters" in permissions,
        )


def validate_key(key: models.APIKey):
    perms = get_key_permissions(key)
    if perms is None:
        raise InvalidAPIKeyError(key=key)
    if not all(perms.values()):
        missing_perms = [k for k, v in perms.items() if not v]
        raise PermissionError(*missing_perms)


def is_key_valide(key: models.APIKey) -> bool:
    try:
        validate_key(key)
        return True
    except GW2APIError:
        return False


def _unwrap_slot(slot: _Slot) -> tuple[str, int]:
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


async def _gather(*tasks: abc.Awaitable[T]) -> tuple[T, ...]:
    async def collect(results: list[T], index: int, task: abc.Awaitable[T]):
        results[index] = await task

    results: list[T] = [Any] * len(tasks)
    async with trio.open_nursery() as nursery:
        for index, task in enumerate(tasks):
            nursery.start_soon(collect, results, index, task)

    return tuple(results)


async def call_api(
    session: asks.Session, url: yarl.URL, key: models.APIKey = None
) -> Any:
    headers = {}
    if key is not None:
        headers = get_headers(key)
    response = session.get(url, headers=headers)
    if response.status == _HTTP_OK:
        return response.json()
    else:
        raise GW2APIError(f"Could not reach {url}: {response}")


async def get_account_inventory(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    slots: list[_Slot] = await call_api(session, _URLS.ACCOUNT_INVENTORY, key)
    return models.Inventory(dict(map(_unwrap_slot, slots)))


async def get_bank_inventory(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    slots: list[_Slot] = await call_api(session, _URLS.BANK_INVENTORY, key)
    return models.Inventory(dict(map(_unwrap_slot, slots)))


async def get_bank_materials(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    slots: list[_Slot] = await call_api(session, _URLS.BANK_MATERIALS, key)
    return models.Inventory(dict(map(_unwrap_slot, slots)))


async def get_character_inventory(
    session: asks.Session, key: models.APIKey, character: str
) -> models.Inventory:
    # character name will be http-encoded by asks library
    url = _URLS.CHARACTER_INVENTORY.with_path(
        _URLS.CHARACTER_INVENTORY.path.format(character=character)
    )
    bags: list[list[_Slot]] = await call_api(session, url, key)
    return sum(
        (models.Inventory(dict(map(_unwrap_slot, bag))) for bag in bags if bag),
        start=models.Inventory(),
    )


async def get_characters_inventories(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    character_names: list[str] = await call_api(session, _URLS.CHARACTER_LIST, key)
    inventories = await _gather(
        *(
            get_character_inventory(session, key, character)
            for character in character_names
        )
    )
    return sum(inventories, start=models.Inventory())


async def get_aggregated_inventory(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    inventories = await _gather(
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
    return sum(inventories, start=models.Inventory())


async def get_wallet(session: asks.Session, key: models.APIKey) -> models.Inventory:
    currencies_list: list[_Slot] = await call_api(session, _URLS.ACCOUNT_WALLET, key)
    return models.Inventory(dict(map(_unwrap_slot, currencies_list)))


async def get_snapshot(session: asks.Session, key: models.APIKey) -> models.Snapshot:
    inventory, wallet = await _gather(
        get_aggregated_inventory(session, key), get_wallet(session, key)
    )
    return models.Snapshot(key=key, inventory=inventory, wallet=wallet)


async def get_items_prices(
    session: asks.Session, item_ids: list[str]
) -> dict[str, tuple[int, int]]:
    """
    get the highest buy offer and lowest sell offer of items
    """
    url = _URLS.ITEM_PRICES % {"ids": ",".join(item_ids)}
    listings: list[_ItemPrices] = await call_api(session, url)
    return {
        str(data["id"]): (data["buys"]["unit_price"], data["sells"]["unit_price"])
        for data in listings
    }


async def get_items_data(
    session: asks.Session, item_ids: list[str]
) -> dict[str, _ItemData]:
    url = _URLS.ITEM_DATA % {"ids": ",".join(item_ids)}
    data: list[_ItemData] = await call_api(session, url)
    for d in data:
        if _FLAG_NO_SELL in d["flags"]:
            d["vendor_value"] = 0
    return {str(d["id"]): d for d in data}


async def download_images(
    session: asks.Session, urls: list[yarl.URL], target_dir: Path
):
    target_dir.mkdir(parents=True, exist_ok=True)

    async def download_image(session: asks.Session, url: yarl.URL, target_dir: Path):
        r = await session.get(str(url), stream=True)
        async with await trio.open_file(target_dir / url.name, "wb") as file:
            async with r.body as content:
                async for chunk in content:
                    await file.write(chunk)

    async with trio.open_nursery() as nursery:
        for url in urls:
            nursery.start_soon(download_image, session, url, target_dir)


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
