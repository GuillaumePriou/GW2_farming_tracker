# -*- coding: utf-8 -*-
import tkinter as tk

from gw2_tracker import controller, model, view


class GW2Tracker(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("GW2 farming tracker")

        # create a model
        model_ = model.Model()

        # create a view and place it on the root window
        view_ = view.View(self)
        view_.grid(row=0, column=0, padx=10, pady=10)

        # create a controller
        controller_ = controller.Controller(model_, view_)

        # set the controller to view
        view_.set_controller(controller_)
