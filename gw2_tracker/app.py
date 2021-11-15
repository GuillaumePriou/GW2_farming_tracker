# -*- coding: utf-8 -*-
import tkinter as tk

from gw2_tracker import controller, model, view


class GW2Tracker(tk.Tk):
    model: model.Model
    controller: controller.Controller
    view: view.View

    def __init__(self):
        super().__init__()

        self.title("GW2 farming tracker")

        # create a model
        self.model = model.Model()

        # create a view and place it on the root window
        self.view = view.View(self)
        self.view.grid(row=0, column=0, padx=10, pady=10)

        # create a controller
        self.controller = controller.Controller(self.model, self.view)

        # set the controller to view
        self.view.set_controller(self.controller)
