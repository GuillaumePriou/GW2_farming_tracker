# -*- coding: utf-8 -*-:
"""
View layer of GW2 tool to evaluate gold earnings.

@author: Krashnark
"""

import logging
from typing import Awaitable, Callable, ParamSpec

import asks
import outcome
import trio

from gw2_tracker import gw2_api, models, protocols, utils

LOGGER = logging.getLogger(__name__)

_MESSAGES = {
    models.States.STARTED: "Welcome. Enter a valid GW2 API key",
    models.States.KEY: "Key is valid. Click to save start inventory",
    models.States.SNAP_START: "Start inventory saved. Click to compute gains",
}

P = ParamSpec("P")


class TrioGuest:
    started: bool = False
    host: None | protocols.TrioHostProto = None
    nursery: trio.Nursery
    session: asks.Session

    def run_in(self, host: protocols.TrioHostProto):
        self.host = host
        trio.lowlevel.start_guest_run(
            self._main,
            run_sync_soon_not_threadsafe=host.run_sync_soon_not_threadsafe,
            run_sync_soon_threadsafe=host.run_sync_soon_threadsafe,
            done_callback=host.done_callback,
            host_uses_signal_set_wakeup_fd=host.uses_signal_set_wakeup_fd,
        )

    async def _main(self):
        self.session = asks.Session(connections=20)
        async with trio.open_nursery() as nursery:
            self.nursery = nursery
            self.started = True
            nursery.start_soon(trio.sleep_forever)

    def start_soon(
        self, task: Callable[P, Awaitable], *args: P.args, **kwargs: P.kwargs
    ):
        if kwargs:
            raise RuntimeError("trio.Nursery.start_soon doesn't support kwargs")
        # self.nursery.start_soon(task, *args)
        self.nursery.parent_task.context.run(self.nursery.start_soon, task, *args)


class Controller:
    model: models.Model
    view: protocols.ViewProto
    trio_guest: TrioGuest

    def __init__(self, model: models.Model, view: protocols.ViewProto):
        self.model = model
        self.view = view
        self.trio_guest = TrioGuest()

        if self.model.current_key is not None:
            self.view.display_key(self.model.current_key)

        self._update_view()

    def _update_view(self):
        if self.model.state >= models.States.KEY:
            self.view.enable_get_start_snapshot()
        if self.model.state >= models.States.SNAP_START:
            self.view.enable_compute_gains()
        if self.model.state in _MESSAGES:
            self.view.display_message(_MESSAGES[self.model.state])

    def start_trio_guest(self, host: protocols.TrioHostProto):
        if self.trio_guest.host is not None:
            if not self.trio_guest.started:
                msg = "guest-mode trio is currently starting"
            else:
                msg = "guest-mode trio is already started"
            msg += f" with host {self.trio_guest.host}"
            raise RuntimeError(msg)
        self.trio_guest.run_in(host)

    def close_app(self):
        LOGGER.debug("closing the app: cancelling trio event loop...")
        self.trio_guest.nursery.cancel_scope.cancel()

    def use_key(self, key: models.APIKey) -> None:
        LOGGER.info(f"validating key {key}")
        self.trio_guest.start_soon(
            gw2_api.validate_key, self.trio_guest.session, key, self._use_key_callback
        )

    async def _use_key_callback(self, key: models.APIKey, out: outcome.Outcome):
        """
        handles the part after the key validation
        """
        if isinstance(out, outcome.Error):
            err: BaseException = out.error
            self.view.display_error(err)
        else:
            LOGGER.info(f"Using and saving key {key}")
            self.model.set_key(key, trio_guest=self.trio_guest)
            self._update_view()
        self.view.enable_key_input()

    def get_start_snapshot(self) -> None:
        if self.model.state < models.States.KEY:
            LOGGER.error("Cannot retrieve a snapshot without a key")
            self._update_view()
        else:
            self.trio_guest.start_soon(self._get_start_snapshot)

    async def _get_start_snapshot(self):
        if self.model.current_key is None:
            LOGGER.error("No saved current key, cannot retrieve snapshot !")
            self._update_view()
        else:
            LOGGER.info("retrieving start snapshot...")
            snapshot = await gw2_api.get_snapshot(
                self.trio_guest.session, self.model.current_key
            )
            LOGGER.info("Setting and saving retrieved snapshot")
            self.model.set_start_snapshot(snapshot, trio_guest=self.trio_guest)
            self.view.enable_get_start_snapshot()
            self._update_view()

    def compute_gains(self) -> None:
        if self.model.state < models.States.SNAP_START:
            LOGGER.error("Cannot compute gains without a start snapshot")
            self._update_view()
        else:
            self.trio_guest.start_soon(self._compute_gains)

    async def _compute_gains(self) -> None:
        if self.model.current_key is None or self.model.start_snapshot is None:
            LOGGER.error("No current key or start snapshot, cannot compute gains")
            self._update_view()
        else:
            LOGGER.info("retrieving end snapshot")
            self.view.display_message("Retrieving end snapshot...")
            snapshot = await gw2_api.get_snapshot(
                self.trio_guest.session, self.model.current_key
            )
            LOGGER.info("Setting and saving retrieved snapshot")
            self.model.set_end_snapshot(snapshot, trio_guest=self.trio_guest)

            if self.model.end_snapshot is None:
                LOGGER.error("No end snapshot after setting it !")
                self._update_view()
                return

            LOGGER.info("Computing differences...")
            inv_diff = (
                self.model.end_snapshot.inventory - self.model.start_snapshot.inventory
            )
            wallet_diff = (
                self.model.end_snapshot.wallet - self.model.start_snapshot.wallet
            )

            LOGGER.info("retrieving item data...")
            self.view.display_message("Retrieving item data...")
            # TODO: use cache and cache item data
            # await self.cache.ensure_cached(inv_diff.keys())
            item_data, prices = await utils.gather(
                gw2_api.get_items_data(self.trio_guest.session, list(inv_diff.keys())),
                gw2_api.get_items_prices(
                    self.trio_guest.session, list(inv_diff.keys())
                ),
            )

            LOGGER.info("computing report...")
            item_details = {
                id_: models.ItemDetail(
                    id=id_,
                    name=item_data[id_]["name"],
                    vendor_value=item_data[id_]["vendor_value"],
                    highest_buy=prices[id_][0],
                    lowest_sell=prices[id_][0],
                )
                for id_ in inv_diff.keys()
            }
            report = models.Report(
                start_date=self.model.start_snapshot.datetime,
                end_date=self.model.end_snapshot.datetime,
                inv_diff=inv_diff,
                wallet_diff=wallet_diff,
                item_details=item_details,
            )
            self.model.set_report(report, trio_guest=self.trio_guest)
            self.view.enable_compute_gains()
            self.view.display_report(report)
