from pathlib import Path

from gw2_tracker import app, utils

CONFIG: utils.SimpleNamespace[Path] = utils.SimpleNamespace(
    base=(base := Path("./gw2_tracker_data")),
    config=base / "config.json",
    model=base / "model.json",
    cache=base / "cache",
)


def main():
    instance = app.GW2Tracker()
    instance.start()
