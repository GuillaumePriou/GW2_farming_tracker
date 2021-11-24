# -*- coding: utf-8 -*-:
"""
View layer of GW2 tool to evaluate gold earnings.

@author: Krashnark
"""

import asks
import trio

from gw2_tracker import models, protocols

_MESSAGES = {
    models.States.STARTED: "Welcome. Enter a valid GW2 API key",
    models.States.KEY: "Key is valid. Click to save start inventory",
    models.States.SNAP_START: "Start inventory saved. Click to compute gains",
}


class GuestTrio:
    started: bool = False
    host: None | protocols.TrioHostProto = None
    nursery: trio.Nursery
    session: asks.Session

    def start(self, host: protocols.TrioHostProto):
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
            await trio.sleep_forever()

    def start_soon(self, task, *args):
        self.nursery.start_soon(task, *args)


class Controller:
    model: models.Model
    view: protocols.ViewProto
    guest_trio: GuestTrio

    def __init__(self, model: models.Model, view: protocols.ViewProto):
        self.model = model
        self.view = view
        self.guest_trio = GuestTrio()

        if self.model.current_key is not None:
            self.view.display_key(self.model.current_key)

        if self.model.state in _MESSAGES:
            self.view.display_message(_MESSAGES[self.model.state])

    def start_trio_guest(self, host: protocols.TrioHostProto):
        if self.guest_trio.host is not None:
            if not self.guest_trio.started:
                msg = "guest-mode trio is currently starting"
            else:
                msg = "guest-mode trio is already started"
            msg += f" with host {self.guest_trio.host}"
            raise RuntimeError(msg)
        self.guest_trio.start(host)

    def save_api_key(self, api_key_input):
        try:
            # self.view.show_action_in_progress('Vérification de la clé...')
            self.model.set_new_key(api_key_input)
            self.view.show_success(
                "Clé validée. Définissez l'inventaire de départ (référence)"
            )
        except ValueError as error:
            # show an error message
            self.view.show_error(error)

    def set_reference_inventory(self):
        try:
            # self.view.show_action_in_progress('Récupération de l\'inventaire via l\'API...')
            self.model.set_reference_inventory()
            self.view.show_success(
                "Inventaire de départ défini. Jouez puis calculez vos gains."
            )
        except ValueError as error:
            self.view.show_error(error)

    def compute_gains(self):
        try:
            print("Controller : begin compute gains & begin get new inventory")
            # self.view.show_action_in_progress('Récupération de l\'inventaire via l\'API et calcul des changements...')
            self.model.get_inventory_and_compare_it()
            print("Controller : end get new inventory. Show success.")
            # self.model.report.compute()
            self.view.show_success("Comparaison achevée.")
            print("Controller : begin display report")
            self.view.display_report(self.model.report)
            print("Controller : end display report & end compute gains")
        except ValueError as error:
            self.view.show_error(error)
