__version__ = "0.1.0"

from gw2_tracker import app


def main():
    instance = app.GW2Tracker()
    instance.mainloop()
