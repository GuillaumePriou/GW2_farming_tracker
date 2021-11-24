# -*- coding: utf-8 -*-
from pathlib import Path

from gw2_tracker import controllers, models, protocols, views


class GW2Tracker:
    model: models.Model
    controller: protocols.ControllerProto
    view: protocols.ViewProto

    def __init__(self, model_file: Path, cache_dir: Path):
        if model_file.is_file():
            self.model = models.Model.from_file(model_file)
        else:
            model_file.parent.mkdir(parents=True, exist_ok=True)
            self.model = models.Model(model_file)
        self.view = views.TkView()
        self.controller = controllers.Controller(self.model, self.view)
        self.view.set_controller(self.controller)

    def start(self):
        self.controller.start_trio_guest(self.view.get_trio_host())
        self.view.start_ui()
