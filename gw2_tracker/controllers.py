# -*- coding: utf-8 -*-:
"""
View layer of GW2 tool to evaluate gold earnings.

@author: Krashnark
"""

import asks
import trio

from gw2_tracker import protocols


class TrioGuest:
    started: bool = False
    nursery: trio.Nursery
    session: asks.Session

    def start(self, host: protocols.TrioHostProto):
        trio.lowlevel.start_guest_run(
            self._main,
            run_sync_soon_not_threadsafe=host.run_sync_soon_not_threadsafe,
            run_sync_soon_threadsafe=host.run_sync_soon_threadsafe,
            done_callback=host.done_callback,
            # TODO: change this if tkinter use it
            host_uses_signal_set_wakeup_fd=host.uses_signal_set_wakeup_fd,
        )

    async def _main(self):
        self.session = asks.Session(connections=20)
        async with trio.open_nursery() as nursery:
            self.nursery = nursery
            self.started = True
            await trio.sleep_forever()


class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

        if self.model.applicationState == "0 - started":
            initial_msg_to_display = (
                "Bienvenue. saissisez une clé API Guild Wars 2 valide."
            )
        elif self.model.applicationState == "1 - got api key":
            initial_msg_to_display = (
                "Clé validée. Définissez l'inventaire de départ (référence)"
            )
        elif self.model.applicationState == "2 - got start inventory":
            initial_msg_to_display = (
                "Inventaire de départ défini. Jouez puis calculez vos gains."
            )

        self.view.refresh_api_key_entry_content(self.model.apiKey.keyValue)
        self.view.show_success(initial_msg_to_display)

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