# -*- coding: utf-8 -*-
from gw2_tracker import controllers, models, protocols, views


class GW2Tracker:
    model: models.Model
    controller: protocols.ControllerProto
    view: protocols.ViewProto

    def __init__(self):
        self.model = models.Model()
        self.view = views.TkView()
        self.controller = controllers.Controller(self.model, self.view)
        self.view.set_controller(self.controller)

    def start(self):
        self.controller.start_trio_guest(self.view.get_trio_host())
        self.view.start_ui()
