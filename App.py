# -*- coding: utf-8 -*-
"""
Created on Mon Nov  1 15:06:21 2021

@author: User
"""

import tkinter as tk

import View as v
import Model as m
import Controller as c

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title('GW2 farming tracker')

        # create a model
        model = m.Model()

        # create a view and place it on the root window
        view = v.View(self)
        view.grid(row=0, column=0, padx=10, pady=10)

        # create a controller
        controller = c.Controller(model, view)

        # set the controller to view
        view.set_controller(controller)


if __name__ == '__main__':
    app = App()
    app.mainloop()