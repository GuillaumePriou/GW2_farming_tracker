import collections
import tkinter as tk
import traceback
from typing import Awaitable, Callable, ClassVar, ParamSpec

import attr
import outcome
import sniffio
import trio

P = ParamSpec("P")


@attr.define
class TkTrioHost:
    # from https://github.com/richardsheridan/trio-guest/blob/master/trio_guest_tkinter.py
    uses_signal_set_wakeup_fd: ClassVar[bool] = False

    _root: tk.Tk
    _queue: collections.deque = attr.field(factory=collections.deque, init=False)
    _tk_func_name: str = attr.field(init=False)

    def __attrs_post_init__(self):
        self._tk_func_name = self._root.register(self._tk_func)

    def _tk_func(self):
        # call a queued func
        self._queue.popleft()()

    def run_sync_soon_threadsafe(self, func):
        self._queue.append(func)
        self._root.call("after", "idle", self._tk_func_name)

    def run_sync_soon_not_threadsafe(self, func):
        self._queue.append(func)
        self._root.call("after", "idle", "after", 0, self._tk_func_name)

    def done_callback(self, trio_outcome: outcome.Outcome):
        print(
            f"Trio loop has closed with outcome {trio_outcome}, stopping tkinter UI..."
        )
        if isinstance(trio_outcome, outcome.Error):
            err = trio_outcome.error
            traceback.print_exception(type(err), err, err.__traceback__)
        self._root.destroy()


class TrioGuest:
    started: bool = False
    host: None | TkTrioHost = None
    nursery: trio.Nursery

    def run_in(self, host: TkTrioHost):
        self.host = host
        trio.lowlevel.start_guest_run(
            self._main,
            run_sync_soon_not_threadsafe=host.run_sync_soon_not_threadsafe,
            run_sync_soon_threadsafe=host.run_sync_soon_threadsafe,
            done_callback=host.done_callback,
            host_uses_signal_set_wakeup_fd=host.uses_signal_set_wakeup_fd,
        )

    async def _main(self):
        async with trio.open_nursery() as nursery:
            self.nursery = nursery
            self.started = True
            nursery.start_soon(trio.sleep_forever)

    def start_soon(
        self, task: Callable[P, Awaitable], *args: P.args, **kwargs: P.kwargs
    ):
        if kwargs:
            raise RuntimeError("trio.Nursery.start_soon doesn't support kwargs")
        self.nursery.start_soon(task, *args)
        #self.nursery.parent_task.context.run(self.nursery.start_soon, task, *args)


async def try_pure_trio():
    print("Before sleep")
    await trio.sleep(3)
    print("After sleep")


async def try_sniffio():
    print(sniffio.current_async_library())


root = tk.Tk()

host = TkTrioHost(root)
guest = TrioGuest()

button_trio = tk.Button(
    root, text="trio", command=lambda: guest.start_soon(try_pure_trio)
)
button_trio.pack()

button_sniffio = tk.Button(
    root, text="sniffio", command=lambda: guest.start_soon(try_sniffio)
)
button_sniffio.pack()

guest.run_in(host)
root.mainloop()
