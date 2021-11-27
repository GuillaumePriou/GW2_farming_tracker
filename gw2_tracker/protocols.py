"""
Module containing protocols used for typechecking

This module also provide a sort of specification
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, ClassVar, ParamSpec, Protocol

import outcome

if TYPE_CHECKING:
    # prevent circular imports due to typechecking
    from gw2_tracker import models

P = ParamSpec("P")


class TrioHostProto(Protocol):
    """
    Protocol for running trio in a host event loop using trio guest mode.

    An object implementing this protocol is used by the controller to run
    network code in parallel with the UI event loop. The object should be
    implemented by the view to run trio whithin the UI event loop.
    """

    uses_signal_set_wakeup_fd: ClassVar[bool]

    def run_sync_soon_threadsafe(self, func: Callable) -> None:
        """
        Must schedule execution of func and be threadsafe.

        See also:
            `trio.lowlevel.start_guest_run`
        """
        ...

    def run_sync_soon_not_threadsafe(self, func: Callable) -> None:
        """
        Must schedule execution of func. Need not be threadsafe.

        If a more efficient implementation of ``run_sync_soon`` is available
        if not thread safety is required, this is useful for performances
        """
        ...

    def done_callback(self, out: outcome.Outcome) -> None:
        """
        Called when the trio event loop has finished. This should terminate
        the host loop.

        When running trio in guest mode, it is best to terminate both the host
        event loop and trio's event loop at the same time. The host loop should
        implement this function to terminate itself, and stop the whole program
        by stopping trio's event loop. This way, both loops start and end at the
        same time.
        """
        ...


class TrioGuestProto(Protocol):
    """
    Used to schedule a coroutine in a guest run of trio
    """

    def run_in(self, host: TrioHostProto) -> None:
        """Starts a main trio function in guest mode"""
        ...

    def start_soon(
        self, task: Callable[P, Awaitable], *args: P.args, **kwargs: P.kwargs
    ):
        """Schedule an awaitable to be run by guest-mode trio"""
        ...


class ControllerProto(Protocol):
    """
    Protocol implemented by controllers

    The view will call this protocol upon UI interaction
    """

    def __init__(self, cache: models.Cache, model: models.Model, view: ViewProto):
        ...

    def start_trio_guest(self, host: TrioHostProto) -> None:
        """Starts trio in guest mode"""
        ...

    def on_ui_start(self) -> None:
        """Called by the view to notifyy the controller that the UI is available"""
        ...

    def close_app(self):
        """Stops the app

        Called by the view to notify the controller to close the app. This is
        necessary because only the controller has access to the trio guest run.
        The view provides a `TrioHostProto` that nows how to stop the GUI part
        in it's ``done_callback`` method. The controller stops the trio guest
        run, which once stopped calls the callback to terminate the UI. This
        way, the UI and the trio loops always run and end at the same time."""
        ...

    def use_key(self, key: models.APIKey):
        """
        Use a new key as the current key. Raises if the key is invalid

        Arguments:
            key: API key to use

        Raises:

        """
        ...

    def get_start_snapshot(self) -> None:
        """retrieve a snapshot for the key and set it as the starting point"""
        ...

    def compute_gains(self) -> None:
        """retrieve a final snapshot and compute gains"""
        ...


class ViewProto(Protocol):
    """
    Protocol for View objects used by the app

    View objects are responsible for handling the display and the main UI event
    loop of the app.
    """

    def get_trio_host(self) -> TrioHostProto:
        """Provide a host that a controller can use to run trio"""
        ...

    def set_controller(self, controller: ControllerProto) -> None:
        ...

    def start_ui(self) -> None:
        """Start the UI event loop"""
        ...

    def display_message(self, msg: str) -> None:
        """Displaty the main message"""
        ...

    def display_error(self, err: BaseException) -> None:
        """Display an exception"""
        ...

    def display_key(self, key: models.APIKey) -> None:
        """Display the current used API key"""
        ...

    async def display_report(self, report: models.Report) -> None:
        """Display a report"""
        ...

    def enable_key_input(self) -> None:
        """Enable key input

        This is called by the controller when the last key validation is done
        and another may be attempted. This is to avoid several key validation
        racing with each other
        """
        ...

    def enable_get_start_snapshot(self) -> None:
        """Enable asking the controller to take a start snapshot"""
        ...

    def enable_compute_gains(self) -> None:
        """Enable asking the controller to retrieve end snapshot and compute gains"""
        ...
