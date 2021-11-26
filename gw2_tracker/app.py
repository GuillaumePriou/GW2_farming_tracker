# -*- coding: utf-8 -*-
import logging
from pathlib import Path

from gw2_tracker import controllers, models, protocols, views

LOGGER = logging.getLogger(__name__)


class GW2Tracker:
    model: models.Model
    controller: protocols.ControllerProto
    view: protocols.ViewProto

    def __init__(self, model_file: Path, cache_dir: Path):
        if model_file.is_file():
            try:
                self.model = models.Model.from_file(model_file)
            except Exception as err:
                LOGGER.error(
                    f"Could not reload saved state from {model_file}, creating new one",
                    exc_info=err,
                )
        if not hasattr(self, "model"):
            model_file.parent.mkdir(parents=True, exist_ok=True)
            self.model = models.Model(model_file)
        self.view = views.TkView()
        self.controller = controllers.Controller(self.model, self.view)
        self.view.set_controller(self.controller)

    def start(self):
        self.controller.start_trio_guest(self.view.get_trio_host())
        self.view.start_ui()
