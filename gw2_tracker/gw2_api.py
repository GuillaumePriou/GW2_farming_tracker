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
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Final,
    Generator,
    Iterable,
    Mapping,
    NewType,
    TypeAlias,
    TypedDict,
    TypeVar,
)

import asks
import attr
import outcome
import requests
import trio
import yarl
from outcome import Error, Value

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
_HTTP_PARTIAL: Final[int] = 206
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


@attr.define
class GW2APIError(Exception):
    """
    Base class for API related error
    """

    msg: str

    def __str__(self) -> str:
        return self.msg


@utils.autoformat
@attr.define
class APIKeyError(GW2APIError):
    """Base class for API Key-related errors"""

    key: models.APIKey


@utils.autoformat
@attr.define
class InvalidAPIKeyError(APIKeyError):
    msg: str = "Invalid API Key '{key}'"


@utils.autoformat
@attr.define
class KeyPermissionError(APIKeyError):
    """
    Insufficient permission on an API key
    """

    missing_perms: tuple[str, ...]
    msg: str = "API Key {key} does not have the required permissions {missing_perms}"


def _get_headers(key: models.APIKey) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def get_key_permissions_sync(key: models.APIKey) -> KeyPermissions | None:
    response = requests.get(str(_URLS.KEY_INFO), headers=_get_headers(key))
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


async def get_key_permissions(
    session: asks.Session, key: models.APIKey
) -> KeyPermissions:
    """
    Returns the permissions an API key provides
    """
    content = await call_api(session, _URLS.KEY_INFO, key=key)
    permissions: KeyPermissions = content["permissions"]
    return KeyPermissions(
        wallet="wallet" in permissions,
        inventories="inventories" in permissions,
        characters="characters" in permissions,
    )


async def validate_key(
    session: asks.Session,
    key: models.APIKey,
    callback: Callable[[models.APIKey, outcome.Outcome], Awaitable],
) -> None:
    """
    Validate that an API key has all the necessary permissions

    Arguments:
        sessions: http session to use to connect to the API
        key: key to test
        callback: async function accepting the tested key and an `Outcome`. The
            outcome will be either an `Error` instance with the encountered
            error, or `Value(True)`
    """
    perms_out: Value | Error = await outcome.acapture(get_key_permissions, session, key)
    if isinstance(perms_out, Error):
        await callback(key, perms_out)
    else:
        perms: KeyPermissions = perms_out.unwrap()
        if not all(perms.values()):
            missing_perms = [k for k, v in perms.items() if not v]
            err = Error(KeyPermissionError(key=key, missing_perms=tuple(missing_perms)))  # type: ignore
            await callback(key, err)
        else:
            await callback(key, Value(True))  # type: ignore


def validate_key_sync(key: models.APIKey):
    perms = get_key_permissions_sync(key)
    if perms is None:
        raise InvalidAPIKeyError(key=key)
    if not all(perms.values()):
        missing_perms = [k for k, v in perms.items() if not v]
        raise KeyPermissionError(key=key, missing_perms=tuple(missing_perms))


def is_key_valide_sync(key: models.APIKey) -> bool:
    try:
        validate_key_sync(key)
        return True
    except GW2APIError:
        return False


def _unwrap_slot(slot: _Slot) -> tuple[models.ItemID, int]:
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
            raise ValueError(f"Invalid slot: <{slot}>")
    return models.ItemID(str(slot["id"])), count


def _slots_to_dict(slots: list[_Slot]) -> dict[models.ItemID, int]:
    try:
        return dict(map(_unwrap_slot, filter(None, slots)))
    except ValueError as err:
        raise ValueError(
            "Invalid slots:\n[\n %s\n]" % (",\n ".join(map(str, slots)))
        ) from err


async def call_api(
    session: asks.Session, url: yarl.URL, key: models.APIKey = None
) -> Any:
    headers = {}
    if key is not None:
        headers = _get_headers(key)
    response = await session.get(str(url), headers=headers)
    if response.status_code in (_HTTP_OK, _HTTP_PARTIAL):
        return response.json()
    else:
        raise GW2APIError(f"Could not reach {url}: {response}")


async def get_account_inventory(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    slots: list[_Slot] = await call_api(session, _URLS.ACCOUNT_INVENTORY, key)
    return models.Inventory(_slots_to_dict(slots))


async def get_bank_inventory(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    slots: list[_Slot] = await call_api(session, _URLS.BANK_INVENTORY, key)
    return models.Inventory(_slots_to_dict(slots))


async def get_bank_materials(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    slots: list[_Slot] = await call_api(session, _URLS.BANK_MATERIALS, key)
    return models.Inventory(_slots_to_dict(slots))


async def get_character_inventory(
    session: asks.Session, key: models.APIKey, character: str
) -> models.Inventory:
    # character name will be http-encoded by asks library
    url = _URLS.CHARACTER_INVENTORY.with_path(
        _URLS.CHARACTER_INVENTORY.path.format(character=character)
    )
    content = await call_api(session, url, key)
    bags: list[list[_Slot]] = [b["inventory"] for b in content["bags"] if b]
    return sum(
        (models.Inventory(_slots_to_dict(bag)) for bag in bags if bag),
        start=models.Inventory(),
    )


async def get_characters_inventories(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    character_names: list[str] = await call_api(session, _URLS.CHARACTER_LIST, key)
    inventories = await utils.gather(
        *(
            get_character_inventory(session, key, character)
            for character in character_names
        )
    )
    return sum(inventories, start=models.Inventory())


async def get_aggregated_inventory(
    session: asks.Session, key: models.APIKey
) -> models.Inventory:
    inventories = await utils.gather(
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
    return models.Inventory(_slots_to_dict(currencies_list))


async def get_snapshot(session: asks.Session, key: models.APIKey) -> models.Snapshot:
    inventory, wallet = await utils.gather(
        get_aggregated_inventory(session, key), get_wallet(session, key)
    )
    return models.Snapshot(key=key, inventory=inventory, wallet=wallet)


async def get_items_prices(
    session: asks.Session, item_ids: list[models.ItemID]
) -> dict[models.ItemID, tuple[None | int, None | int]]:
    """
    get the highest buy offer and lowest sell offer of items
    """
    if not item_ids:
        return {}
    # TODO: handle no offers w/ None values
    url = _URLS.ITEM_PRICES % {"ids": ",".join(item_ids)}
    listings: list[_ItemPrices] = await call_api(session, url)
    return {
        models.ItemID(str(data["id"])): (
            data.get("buys", {}).get("unit_price"),
            data.get("sells", {}).get("unit_price"),
        )
        for data in listings
    }


async def get_items_data(
    session: asks.Session, item_ids: list[models.ItemID]
) -> dict[models.ItemID, models.ItemData]:
    if not item_ids:
        return {}
    url = _URLS.ITEM_DATA % {"ids": ",".join(item_ids)}
    data: list[models.ItemData] = await call_api(session, url)
    for d in data:
        if _FLAG_NO_SELL in d["flags"]:
            d["vendor_value"] = 0
    return {models.ItemID(str(d["id"])): d for d in data}


async def download_images(
    session: asks.Session, urls: Mapping[yarl.URL, Path]
) -> dict[yarl.URL, Path]:

    result: dict[yarl.URL, Path] = {}

    async def download_image(
        session: asks.Session,
        url: yarl.URL,
        path: Path,
        result: dict[yarl.URL, Path],
    ):
        r = await session.get(str(url), stream=True)
        async with await trio.open_file(path, "wb") as file:
            async with r.body as content:
                async for chunk in content:
                    await file.write(chunk)
        result[url] = path

    async with trio.open_nursery() as nursery:
        for url, path in urls.items():
            nursery.start_soon(download_image, session, url, path, result)

    return result


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
