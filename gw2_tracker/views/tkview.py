# -*- coding: utf-8 -*-
"""
View layer of GW2 tool to evaluate gold earnings.

@author: Krashnark
"""
from __future__ import annotations

import collections
import functools
import logging
import tkinter as tk
from importlib import abc, resources
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable, ClassVar, Literal

import attr
import outcome

from gw2_tracker import models, protocols, utils

ttk.Frame = ttk.LabelFrame


LOGGER = logging.getLogger(__name__)

ASSET_SOURCES = resources.files("gw2_tracker").joinpath("assets")

ASSETS = {
    k: ASSET_SOURCES.joinpath(f"{k}_coin_20px.png")
    for k in ("copper", "silver", "gold")
}


@attr.define
class TkTrioHost:
    """
    Implementation of the trio host protocol for tkinter

    thanks to https://github.com/richardsheridan/trio-guest/blob/master/trio_guest_tkinter.py
    """

    # TODO: determine what this should be
    uses_signal_set_wakeup_fd: ClassVar[bool] = False

    _root: tk.Tk
    _queue: collections.deque = attr.field(factory=collections.deque, init=False)
    _tk_func_name: str = attr.field(init=False)

    def __attrs_post_init__(self):
        self._tk_func_name = self._root.register(self._tk_func)

    def _tk_func(self):
        # call a queued func
        self._queue.popleft()()

    def run_sync_soon_threadsafe(self, func: Callable) -> None:
        self._queue.append(func)
        self._root.call("after", "idle", self._tk_func_name)

    def run_sync_soon_not_threadsafe(self, func: Callable) -> None:
        self._queue.append(func)
        self._root.call("after", "idle", "after", 0, self._tk_func_name)

    def done_callback(self, out: outcome.Outcome) -> None:
        if isinstance(out, outcome.Error):
            LOGGER.error(
                "Trio loop raised the following exception:", exc_info=out.error
            )
        else:
            LOGGER.debug(f"Trio loop cloed normally ({out})")
        LOGGER.debug("Closing Tk event loop")
        self._root.destroy()


class ScrollableFrame(ttk.Frame):
    """
    Frame automatically embedded in a Canvas with a scrollbar

    This widget first creates a `tk.Canvas` with an attached `ttk.Scrollbar`
    on it before adding itself as a window of the canvas. It should make adding
    a scrollbar to a frame transparent.

    Parameters:
        parent: parent widget to create this frame in. This is not the actual
            parent of this widget, see the ``canvas`` attribute.
        orient: orientation of the scrollbar

    Attributes:
        canvas: the automatically created canvas that is the parent of this
            widget. The parent of the canvas is the ``parent`` passed when
            initializing the `ScrollableFrame`.
        scrollbar: scrollbar of the ``canvas`` attribute

    See also:
        ttk.Frame
    """

    _canvas_: tk.Canvas
    _scrollbar_: ttk.Scrollbar

    def __init__(
        self,
        parent,
        *,
        orient: Literal["vertical", "horizontal"] = "vertical",
        canvas_kws: dict[str, Any] = None,
        scrollbar_kws: dict[str, Any] = None,
        **kwargs,
    ):
        # Create a Canvas between this frame and its parent and add a scrollbar
        self._canvas_ = tk.Canvas(parent, **(canvas_kws or {}))
        self._scrollbar_ = ttk.Scrollbar(
            self._canvas_, orient=orient, **(scrollbar_kws or {})
        )
        if orient == "vertical":
            self._scrollbar_.configure(command=self._canvas_.yview)
            self._canvas_.configure(yscrollcommand=self._scrollbar_.set)
            self._scrollbar_.pack(side="right", fill="y")
        elif orient == "horizontal":
            self._scrollbar_.configure(command=self._canvas_.xview)
            self._canvas_.configure(xscrollcommand=self._scrollbar_.set)
            self._scrollbar_.pack(side="bottom", fill="x")
        self._canvas_.pack(side="left", fill="both", expand=True)

        # Actually initialise the frame and display it in the canvas
        super().__init__(self._canvas_, **kwargs)
        self._canvas_.create_window(
            0, 0, window=self, anchor="nw", tags="scrollable_frame"
        )
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event):
        """
        Adapts the canvas when the frame is resized
        """
        self._canvas_.configure(scrollregion=self._canvas_.bbox("all"))


class CoinWidget(ttk.Frame):
    """Widget displaying a single coin"""

    IMAGE_CACHE: ClassVar[dict[abc.Traversable, tk.PhotoImage]] = {}

    label: ttk.Label
    logo: ttk.Label

    def __init__(self, parent, asset: abc.Traversable, amount: int = 0):
        """
        Parameters:
            parent: parent widget
            asset: asset to display after the amount
        """
        super().__init__(parent)

        if asset not in self.IMAGE_CACHE:
            self.IMAGE_CACHE[asset] = tk.PhotoImage(data=asset.read_bytes())

        self.label = ttk.Label(self, text="-")
        self.logo = ttk.Label(self, image=self.IMAGE_CACHE[asset])

        self.label.pack(side="left")
        self.logo.pack(side="left")

        self.amount = amount

    @property
    def amount(self) -> int:
        return self._amount

    @amount.setter
    def amount(self, value: int):
        self._amount = value
        self.label.config(text=self._amount)


class GoldWidget(ttk.Frame):
    copper: CoinWidget
    silver: CoinWidget
    gold: CoinWidget

    def __init__(self, parent, amount=0):
        super().__init__(parent)

        self.copper = CoinWidget(self, ASSETS["copper"])
        self.silver = CoinWidget(self, ASSETS["silver"])
        self.gold = CoinWidget(self, ASSETS["gold"])

        self.gold.pack(side="left")
        self.silver.pack(side="left")
        self.copper.pack(side="left")

        self.amount = amount

    @property
    def amount(self) -> int:
        return self._amount

    @amount.setter
    def amount(self, value: int):
        self._amount = value
        self.copper.amount = value % 100
        self.silver.amount = (value // 100) % 100
        self.gold.amount = value // 10000


class ReportDetailsWidget(ttk.Frame):
    """
    Widget to display the details of the computed gains.

    This widgets uses the ``grid`` display manager to display table-like
    content. Information displayed are:
        - Item icon
        - Item id (for debug)
        - Item name
        - Item count
        - Black lion price
        - Vendor price
    """

    _LEGENDS: ClassVar[tuple[str, ...]] = (
        "ID",
        "Name",
        "Amount",
        "Black lion value",
        "Vendor value",
    )

    @attr.mutable
    class _Row:
        """Internal helper to handle a row"""

        @staticmethod
        @functools.lru_cache(512)
        def _get_icon(path: Path):
            # Cache icon to avoid reloading common items
            return tk.PhotoImage(file=str(path))

        parent: ReportDetailsWidget
        row: int
        icon: ttk.Label = attr.field(init=False)
        id: ttk.Label = attr.field(init=False)
        name: ttk.Label = attr.field(init=False)
        count: ttk.Label = attr.field(init=False)
        black_lion_price: ttk.Label = attr.field(init=False)
        vendor_price: ttk.Label = attr.field(init=False)

        def __attrs_post_init__(self):
            for col, field in enumerate(
                ("icon", "id", "name", "count", "black_lion_price", "vendor_price")
            ):
                widget = ttk.Label(self.parent, text="-")
                widget.grid(row=self.row, column=col)
                setattr(self, field, widget)

        async def update(self, item_detail: models.ItemDetail, count: int) -> None:
            if item_detail.icon_path is not None:
                self.icon.configure(image=self._get_icon(item_detail.icon_path))
            self.id.configure(text=item_detail.id)
            self.name.configure(text=item_detail.name)
            self.count.configure(text=count)
            if item_detail.value_black_lion:
                self.black_lion_price.configure(text=item_detail.value_black_lion)
            else:
                self.black_lion_price.configure(text="-")
            if item_detail.vendor_value > 0:
                self.vendor_price.configure(text=item_detail.vendor_value)
            else:
                self.vendor_price.configure(text="-")

        def destroy(self):
            self.icon.destroy()
            self.id.destroy()
            self.name.destroy()
            self.count.destroy()
            self.black_lion_price.destroy()
            self.vendor_price.destroy()

    # Instance attributes
    legends: tuple[ttk.Label, ...]
    rows: list[_Row]

    def __init__(self, parent, report: models.Report = None):
        super().__init__(parent)

        # Legends for the details
        legends = []
        for col, legend in enumerate(self._LEGENDS):
            widget = ttk.Label(self, text=legend)
            widget.grid(row=0, column=col + 1)
            legends.append(widget)
        self.legends = tuple(legends)

        self.rows = [self._Row(self, 1)]

    async def update(self, report: models.Report) -> None:
        item_details = [
            report.item_details[id_] for id_ in sorted(report.inv_diff.keys())
        ]
        item_counts = [report.inv_diff[detail.id] for detail in item_details]
        # First re-use rows that already exist:
        index = -1
        for index, (row, detail, count) in enumerate(
            zip(self.rows, item_details, item_counts)
        ):
            await row.update(detail, count)
        index += 1

        if index < len(item_details):
            # Not enought rows to re-use, create new ones
            for offset, (detail, count) in enumerate(
                zip(item_details[index:], item_counts[index:])
            ):
                row = self._Row(self, index + offset + 1)
                self.rows.append(row)
                await row.update(detail, count)
        elif index > len(item_details):
            # Too many rows, destroy & drop extra ones
            for row in self.rows[index:]:
                row.destroy()
            self.rows = self.rows[:index]


class FullReportWidget(ttk.Frame):
    """
    Widget to display a report.

    This widget display the amount of gold earn, as well as the total gain
    from coins and items, and delegates displaying the details.

    Attributes:
        A dedicated frame to display the item gained during a play session.
    Information to be displayed :
        At the top :
        - total gold value earned (aquisition & liquid)
        - Time

        In a table-like form :
        - Item icon
        - Item id (for debug)
        - Item name
        - Item count
        - Aquisition price
        - Liquid gold value
    """

    def __init__(self, parent):
        super().__init__(parent)
        # self.farmTimeLabel = ttk.Label(text='Durée : à calculer')
        # self.farmTimeLabel.grid(row=0, column=0)

        # Total aquisition price display
        self.label_tot_aquisition = ttk.Label(self, text="Total gain")
        self.label_tot_aquisition.grid(row=0, column=0)

        self.gold_tot_acquisition = GoldWidget(self, 0)
        self.gold_tot_acquisition.grid(row=0, column=1)

        self.label_tot_liquid = ttk.Label(self, text="Coin gain")
        self.label_tot_liquid.grid(row=0, column=2)

        self.gold_tot_liquid = GoldWidget(self, 0)
        self.gold_tot_liquid.grid(row=0, column=3)

        self.widget_details = ReportDetailsWidget(self)
        self.widget_details.grid(row=1, column=0, columnspan=4)

        # if report == None:
        #     self.gold_tot_aquisition = Any
        # else:
        #     self.gold_tot_aquisition = GoldWidget(
        #         self, report.totalAquisitionValue
        #     )

        # # Total liquid gold price display
        # self.label_tot_liquid = ttk.Label(self, text="Prix liquid gold")
        # self.label_tot_liquid.grid(row=0, column=2)

        # if report == None:
        #     self.gold_tot_liquid = GoldWidget(self, 0)
        # else:
        #     self.gold_tot_liquid = GoldWidget(
        #         self, report.totalLiquidGoldValue
        #     )

        # if report == None:
        #     self.details = DetailsReportDisplay(self, [])
        # else:
        #     self.details = DetailsReportDisplay(self, report.itemsDetail)

    async def update(self, report: models.Report):
        # TODO: set the gold values
        self.gold_tot_liquid.amount = report.coins
        self.gold_tot_acquisition = report.total_gains
        # Update details
        await self.widget_details.update(report)


class TkView:
    """
    Tk implementation of the View protocols.

    Implements:
        gw2_tracker.protocols.ViewProto
    """

    root: tk.Tk
    controller: protocols.ControllerProto
    host: TkTrioHost

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GW2 farming tracker")
        self.host = TkTrioHost(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _build(self):
        # Define a big important message to help user to use the this application
        self.label_main_message = ttk.Label(
            self.root, text="Hello this is dog.", font="bold"
        )
        self.label_main_message.grid(row=0, column=0, columnspan=3)

        # Entry widget where the user paste his API key
        self.input_key = ttk.Entry(self.root, width=80)
        self.input_key.grid(row=1, column=0, columnspan=2)

        self.button_key = ttk.Button(
            self.root, text="Use key", command=self._on_button_key
        )
        self.button_key.grid(row=1, column=2)

        # Buttons to get inventories and calculate differences

        self.button_start = ttk.Button(
            self.root,
            text="Get start snapshot",
            state="disabled",
            command=self._on_get_start_snapshot,
        )
        self.button_start.grid(row=2, column=0)

        self.button_stop = ttk.Button(
            self.root,
            text="Compute gains",
            state="disabled",
            command=self._on_compute_gains,
        )
        self.button_stop.grid(row=2, column=2)

        self.widget_report = FullReportWidget(self.root)
        self.widget_report.grid(row=3, column=0, columnspan=3)

    def get_trio_host(self) -> TkTrioHost:
        return TkTrioHost(self.root)

    def set_controller(self, controller):
        self.controller = controller

    def start_ui(self) -> None:
        self.root.after(500, self.controller.on_ui_start)
        self.root.mainloop()

    def display_message(self, msg: str) -> None:
        self.label_main_message.configure(text=msg, foreground="black")

    def display_error(self, err: BaseException) -> None:
        # TODO: this is a hack, error should be logged before
        LOGGER.error(utils.err_traceback(err))
        self.label_main_message.configure(text=utils.err_str(err), foreground="red")

    def display_key(self, key: models.APIKey) -> None:
        self.input_key.delete(0, tk.END)
        self.input_key.insert(0, key)

    ###

    def _on_close(self) -> None:
        if hasattr(self, "controller"):
            self.controller.close_app()
        else:
            # No controller, close the windows normally as there is no
            # trio loop to close
            self.root.destroy()

    def _on_button_key(self) -> None:
        if self.controller is None:
            raise RuntimeError("No controller")

        LOGGER.debug("Clicked save api key button")
        self.display_message("Verifying key ...")
        self.button_key.configure(state="disabled")
        self.controller.use_key(models.APIKey(self.input_key.get()))

    def enable_key_input(self) -> None:
        self.button_key.configure(state="normal")

    def _on_get_start_snapshot(self) -> None:
        if self.controller is None:
            raise RuntimeError("No controller")
        self.display_message("Retrieving starting snapshot...")
        self.button_start.configure(state="disabled")
        self.controller.get_start_snapshot()

    def enable_get_start_snapshot(self) -> None:
        self.button_start.configure(state="normal")

    def _on_compute_gains(self):
        if self.controller is None:
            raise RuntimeError("No controller")
        self.display_message("Computing gains...")
        self.button_stop.configure(state="disabled")
        self.controller.compute_gains()

    def enable_compute_gains(self) -> None:
        self.button_stop.configure(state="normal")

    async def display_report(self, report: models.Report) -> None:
        await self.widget_report.update(report)
