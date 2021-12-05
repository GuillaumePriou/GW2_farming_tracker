# -*- coding: utf-8 -*-
"""
Tkinter view for GW2 tracker app

This modules uses the tkinter builtin module to implement the view protocol
required by the GW2 tracker app (see the ``gw2_tracker.protocol`` module).
"""
from __future__ import annotations

import collections
import functools
import logging
import tkinter as tk
from importlib import abc, resources
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable, ClassVar, Concatenate, Generic, ParamSpec, TypeVar

import attr
import outcome
import trio

from gw2_tracker import models, protocols, utils

LOGGER = logging.getLogger(__name__)

ASSET_SOURCES = resources.files("gw2_tracker").joinpath("assets")

ASSETS = {
    k: ASSET_SOURCES.joinpath(f"{k}_coin_20px.png")
    for k in ("copper", "silver", "gold")
}

Parent = TypeVar("Parent", bound=tk.Widget)
Widget = TypeVar("Widget", bound=tk.Widget)
P = ParamSpec("P")


@attr.define
class TkTrioHost:
    """
    Implementation of the trio host protocol for tkinter

    thanks to
    https://github.com/richardsheridan/trio-guest/blob/master/trio_guest_tkinter.py
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


class LabeledWidget(Generic[Widget], ttk.Frame):
    """
    Wrapper widget to add a label before another

    Attributes:
        label: the label widget created
        widget: wrapped widget
    """

    label: ttk.Label
    widget: Widget

    def __init__(
        self,
        parent,
        text,
        /,
        cls: Callable[Concatenate[Parent, P], Widget],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """
        Initialize a new labelled widget

        Arguments:
            parent: parent widget in which to create the label and widget
            text: text of the label
            cls: class of the widget to create (or factory function)
            args: additional arguments to ``cls``
            kwargs: additional arguments to ``cls``
        """
        super().__init__(parent)

        # Use an intermediary frame to center the label+widget
        # without introducing space between the label and widget
        self._frame = ttk.Frame(self)
        self._frame.grid(row=0, column=0, sticky="")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.label = ttk.Label(self._frame, text=text)
        self.widget = cls(self._frame, *args, **kwargs)

        self.label.pack(side="left", ipadx=10)  # expand=True, fill="x")
        self.widget.pack(
            side="right",
        )  # expand=True, fill="x")


class Combobox(ttk.Combobox):
    def __init__(self, parent, values, *args, interactive=True, **kwargs):
        state = "normal" if interactive else "readonly"
        # kwargs.setdefault("widhth", max(len(str(v)) for v in values) + 1)
        values = list(values)
        super().__init__(
            parent, *args, state=state, values=values, **kwargs  # width=width,
        )
        if values:
            self.set(values[0])

    def set_values(self, values):
        selected = self.get()
        values = list(values)
        self.configure(values=values)  # , width=max(len(str(v)) for v in values) + 1)
        self.set(selected if selected in values else values[0])


class AutoScrollbar(ttk.Scrollbar):
    """
    Scrollbar that hides itself when not need

    See also:
        https://stackoverflow.com/questions/30018148/python-tkinter-scrollable-frame-class
    """

    def set(self, low, high):
        if float(low) <= 0.01 and float(high) >= 0.99:
            self.grid_remove()
        else:
            self.grid()
        super().set(low, high)

    def pack(self, *args, **kwargs):
        raise tk.TclError(
            f"{self.__class__.__name__} is not compatible with pack geometry"
        )

    def place(self, *args, **kwargs):
        raise tk.TclError(
            f"{self.__class__.__name__} is not compatible with place geometry"
        )


class ScrollableFrame(ttk.Frame):
    """
    Frame automatically embedded in a Canvas with a scrollbar

    This widget first creates a `tk.Canvas` with an attached `ttk.Scrollbar`
    on it before adding itself as a window of the canvas. It should make adding
    a scrollbar to a frame transparent.

    Parameters:
        parent: parent widget to create this frame in. This is not the actual
            parent of this widget, see the ``canvas`` attribute.
        kwargs: other Tk arguments

    Attributes:
        frame: the inner frame widget should be created in
    """

    vertical_scrollbar: AutoScrollbar
    horizontal_scrollbar: AutoScrollbar
    canvas: tk.Canvas
    frame: ttk.Frame

    def __init__(
        self,
        parent,
        *,
        canvas_kws: dict[str, Any] = None,
        scrollbar_kws: dict[str, Any] = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        # Scrollbars
        self.vertical_scrollbar = AutoScrollbar(
            self, orient=tk.VERTICAL, **(scrollbar_kws or {})
        )
        self.vertical_scrollbar.grid(row=0, column=1, sticky="ns")

        self.horizontal_scrollbar = AutoScrollbar(
            self, orient=tk.HORIZONTAL, **(scrollbar_kws or {})
        )
        self.horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

        # Canvas
        self.canvas = tk.Canvas(
            self,
            xscrollcommand=self.horizontal_scrollbar.set,
            yscrollcommand=self.vertical_scrollbar.set,
            **(canvas_kws or {}),
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Bind scrollbars
        self.vertical_scrollbar.config(command=self.canvas.yview)
        self.horizontal_scrollbar.config(command=self.canvas.xview)

        # Expandable
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Inner frame
        self.frame = ttk.Frame(self.canvas)
        self.canvas.create_window(
            0, 0, anchor="nw", window=self.frame, tags=["canvas_frame"]
        )

        # self.frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_frame_configure(self, event=None):
        """
        Adapts the canvas when the frame is resized
        """
        self.frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # from https://stackoverflow.com/questions/69547008/create-resizable-tkinter-frame-inside-of-scrollable-canvas # noqa: E501
        min_width = self.frame.winfo_reqwidth() + 5
        min_height = self.frame.winfo_reqheight() + 5
        if min_width < event.width:
            self.canvas.itemconfigure("canvas_frame", width=event.width)
        if min_height < event.height:
            self.canvas.itemconfigure("canvas_frame", height=event.height)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


class KeyInputWidget(ttk.Frame):
    """Widget for entering the GW2 API key"""

    label: ttk.Label
    entry: ttk.Entry
    button: ttk.Button

    def __init__(self, parent):
        super().__init__(parent)

        self.label = ttk.Label(self, text="GW2 API key :")
        self.label.pack(side="left", padx=5)

        self.entry = ttk.Entry(self, width=80)
        self.entry.pack(side="left", expand=True, fill="x")

        self.button = ttk.Button(self, text="Use key")
        self.button.pack(side="left", padx=5)


class _SingleCoinWidget(ttk.Frame):
    """Widget displaying a value and coin icon"""

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


class CoinWidget(ttk.Frame):
    """Display monetary values in gold, silver and copper coins"""

    copper: _SingleCoinWidget
    silver: _SingleCoinWidget
    gold: _SingleCoinWidget

    def __init__(self, parent, amount=0):
        super().__init__(parent)

        self.copper = _SingleCoinWidget(self, ASSETS["copper"])
        self.silver = _SingleCoinWidget(self, ASSETS["silver"])
        self.gold = _SingleCoinWidget(self, ASSETS["gold"])

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
        if value < 0:
            value = abs(value)
            self.copper.label.configure(foreground="red")
            self.silver.label.configure(foreground="red")
            self.gold.label.configure(foreground="red")
        else:
            self.copper.label.configure(foreground="black")
            self.silver.label.configure(foreground="black")
            self.gold.label.configure(foreground="black")
        self.copper.amount = value % 100
        self.silver.amount = (value // 100) % 100
        self.gold.amount = value // 10000


class ReportDetailsWidget(ttk.Frame):
    """
    Widget to display the details of the computed gains.

    This widgets uses the ``grid`` display manager to display table-like
    content. Informations displayed are:
        - Item icon
        - Item id (for debug)
        - Item name
        - Item count
        - total value
        - unit black lion value
        - unit vendor price
    """

    _LEGENDS: ClassVar[tuple[str, ...]] = (
        "ID",
        "Name",
        "Amount",
        "total value",
        "unit black lion value",
        "unit vendor value",
    )

    @attr.mutable
    class _Row:
        """Internal helper to handle a row"""

        @staticmethod
        @functools.lru_cache(512)
        def _get_icon(path: Path):
            # Cache icon to avoid reloading common items
            return tk.PhotoImage(file=str(path))

        parent: tk.Widget
        row: int
        icon: ttk.Label = attr.field(init=False)
        id: ttk.Label = attr.field(init=False)
        name: ttk.Label = attr.field(init=False)
        count: ttk.Label = attr.field(init=False)
        total_value: CoinWidget = attr.field(init=False)
        black_lion_value: CoinWidget = attr.field(init=False)
        vendor_value: CoinWidget = attr.field(init=False)

        def __attrs_post_init__(self):
            col = -1
            for col, field in enumerate(("icon", "id", "name", "count")):
                widget = ttk.Label(self.parent, text="-")
                widget.grid(row=self.row, column=col)
                setattr(self, field, widget)
            offset = col + 1
            for col, field in enumerate(
                ("total_value", "black_lion_value", "vendor_value")
            ):
                widget = CoinWidget(self.parent, amount=0)
                widget.grid(row=self.row, column=col + offset)
                setattr(self, field, widget)

        async def update(self, item_detail: models.ItemDetail, count: int) -> None:
            if item_detail.icon_path is not None:
                self.icon.configure(image=self._get_icon(item_detail.icon_path))
            self.id.configure(text=item_detail.id)
            self.name.configure(text=item_detail.name)
            self.count.configure(text=count)
            self.total_value.amount = count * item_detail.value
            if item_detail.value_black_lion:
                self.black_lion_value.amount = item_detail.value_black_lion
            else:
                self.black_lion_value.amount = 0
            self.vendor_value.amount = item_detail.vendor_value
            await trio.sleep(0)

        def destroy(self):
            self.icon.destroy()
            self.id.destroy()
            self.name.destroy()
            self.count.destroy()
            self.total_value.destroy()
            self.black_lion_value.destroy()
            self.vendor_value.destroy()

    # Instance attributes
    scrollable_frame: ScrollableFrame
    legends: tuple[ttk.Label, ...]
    rows: list[_Row]

    def __init__(self, parent):
        super().__init__(parent)

        self.scrollable_frame = ScrollableFrame(self)
        self.scrollable_frame.pack(side="left", expand=True, fill="both")
        self.scrollable_frame.frame.columnconfigure(0, pad=5)

        # Legends for the details
        legends = []
        for col, legend in enumerate(self._LEGENDS):
            widget = ttk.Label(
                self.scrollable_frame.frame, text=legend, font="bold", justify="center"
            )
            widget.grid(row=0, column=col + 1)
            self.scrollable_frame.frame.columnconfigure(col + 1, weight=1, pad=15)
            legends.append(widget)
        self.legends = tuple(legends)

        self.rows = [self._Row(self.scrollable_frame.frame, 1)]

    async def update(self, report: models.Report) -> None:
        details = [report.item_details[id_] for id_ in sorted(report.inv_diff.keys())]
        counts = [report.inv_diff[detail.id] for detail in details]

        # First re-use rows that already exist:
        index = -1
        for index, (row, detail, count) in enumerate(zip(self.rows, details, counts)):
            await row.update(detail, count)
        index += 1

        if index < len(details):
            # Not enought rows to re-use, create new ones
            for offset, (detail, count) in enumerate(
                zip(details[index:], counts[index:])
            ):
                row = self._Row(self.scrollable_frame.frame, index + offset + 1)
                self.rows.append(row)
                await row.update(detail, count)
        elif index > len(details):
            # Too many rows, destroy & drop extra ones
            for row in self.rows[index:]:
                row.destroy()
            self.rows = self.rows[:index]
        LOGGER.debug("ReportsDetailWidget::update() finished")


class FullReportWidget(ttk.Frame):
    """
    Widget to display a report.

    This widget display the amount of gold earn, as well as the total gain
    from coins and items, and delegates displaying the details.

    Attributes:
        header: frame to display monetary values
        total_gain: total value of gold and object earned (or lost)
        coin_gain: coin gained or lost
        details: detailed composition of the report
    """

    header: ttk.Frame
    total_gain: LabeledWidget[CoinWidget]
    coin_gain: LabeledWidget[CoinWidget]
    details: ReportDetailsWidget

    def __init__(self, parent):
        super().__init__(parent)
        self.header = ttk.Frame(self)
        self.header.pack(side="top", fill="x")

        self.total_gain = LabeledWidget(self.header, "Total gain value", CoinWidget)
        self.total_gain.pack(side="left", expand=True, fill="x")

        self._vsep = ttk.Separator(self.header, orient=tk.VERTICAL)
        self._vsep.pack(side="left", fill="y")

        self.coin_gain = LabeledWidget(self.header, "Coin gains", CoinWidget)
        self.coin_gain.pack(side="left", expand=True, fill="x")

        self._hsep = ttk.Separator(self, orient=tk.HORIZONTAL)
        self._hsep.pack(side="top", fill="x")

        self.details = ReportDetailsWidget(self)
        self.details.pack(side="bottom", expand=True, fill="both")

    async def update(self, report: models.Report):
        self.coin_gain.widget.amount = report.coins
        self.total_gain.widget.amount = report.total_gains
        # Update details
        await self.details.update(report)


class TkView:
    """
    Tk implementation of the View protocols.

    Implements:
        gw2_tracker.protocols.ViewProto
    """

    tk_: tk.Tk
    base: ttk.Frame
    controller: protocols.ControllerProto
    host: TkTrioHost

    def __init__(self):
        self.tk_ = tk.Tk()
        self.tk_.title("GW2 tracker")
        self.host = TkTrioHost(self.tk_)
        self.tk_.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _build(self):
        self.base = ttk.Frame(self.tk_)
        self.base.pack(side="left", expand=True, fill="both")
        # Define a big important message to help user to use the this application
        self.label_main_message = ttk.Label(
            self.base,
            text="No message",
            font="bold",
            anchor="center",
            relief="solid",
            background="white",
        )
        self.label_main_message.pack(side="top", fill="x", padx=10, pady=10)

        # Entry widget where the user paste his API key
        self.key_input = KeyInputWidget(self.base)
        self.key_input.pack(side="top", fill="x", padx=10)
        self.key_input.button.config(command=self._on_button_key)

        # Buttons to get inventories and calculate differences
        self.frame_button = ttk.Frame(self.base)
        self.frame_button.pack(side="top", fill="x", padx=10)

        self.button_start = ttk.Button(
            self.frame_button,
            text="Get start snapshot",
            state="disabled",
            command=self._on_get_start_snapshot,
        )
        self.button_start.pack(side="left", expand=True)

        self.button_stop = ttk.Button(
            self.frame_button,
            text="Compute gains",
            state="disabled",
            command=self._on_compute_gains,
        )
        self.button_stop.pack(side="left", expand=True)

        self.widget_report = FullReportWidget(self.base)
        self.widget_report.pack(side="top", expand=True, fill="both", pady=10, padx=10)

    def get_trio_host(self) -> TkTrioHost:
        return TkTrioHost(self.tk_)

    def set_controller(self, controller):
        self.controller = controller

    def start_ui(self) -> None:
        self.base.after(500, self.controller.on_ui_start)
        self.base.mainloop()

    def display_message(self, msg: str) -> None:
        self.label_main_message.configure(text=msg, foreground="black")

    def display_error(self, err: BaseException) -> None:
        # TODO: this is a hack, error should be logged before
        LOGGER.error(utils.err_traceback(err))
        self.label_main_message.configure(text=utils.err_str(err), foreground="red")

    def display_key(self, key: models.APIKey) -> None:
        self.key_input.entry.delete(0, tk.END)
        self.key_input.entry.insert(0, key)

    ###

    def _on_close(self) -> None:
        if hasattr(self, "controller"):
            self.controller.close_app()
        else:
            # No controller, close the windows normally as there is no
            # trio loop to close
            self.base.destroy()

    def _on_button_key(self) -> None:
        if self.controller is None:
            raise RuntimeError("No controller")

        LOGGER.debug("Clicked save api key button")
        self.display_message("Verifying key ...")
        self.key_input.button.configure(state="disabled")
        self.controller.use_key(models.APIKey(self.key_input.entry.get()))

    def enable_key_input(self) -> None:
        self.key_input.button.configure(state="normal")

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
