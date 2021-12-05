# -*- coding: utf-8 -*-
"""
GW2 tracker application

The application object initializes the model, controller and view and starts
the event loops. The GW2 tracker app runs to event loops simultaneously: the
UI event loop and the Trio event loop. Trio is run in guest mode inside the
UI event loop, which must provide a specific API for doing so. See the
``gw2_tracker.protocols`` module for the necessary API.
"""
import logging
from pathlib import Path

from gw2_tracker import controllers, models, protocols, views

LOGGER = logging.getLogger(__name__)


class GW2Tracker:
    model: models.Model
    controller: protocols.ControllerProto
    view: protocols.ViewProto

    def __init__(self, model_file: Path, cache_dir: Path):
        # Create cache
        if cache_dir.is_file():
            raise FileExistsError(f"{cache_dir=} should be a directory but is a file")
        if cache_dir.is_dir():
            cache = models.Cache.from_dir(cache_dir)
        else:
            cache = models.Cache(cache_dir)
        # Init model
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
        # Init view and controller
        self.view = views.TkView()
        self.controller = controllers.Controller(cache, self.model, self.view)
        self.view.set_controller(self.controller)

    def start(self):
        self.controller.start_trio_guest(self.view.get_trio_host())
        self.view.start_ui()
