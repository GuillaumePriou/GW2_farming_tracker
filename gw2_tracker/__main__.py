#!/usr/bin/env python
"""
Main entry-point of the GW2 tracker app

This module is executable using the ``-m`` python flag, and implements a
``main`` function that is the app entry-point.
"""
import sys

if sys.version_info < (3, 10):
    raise RuntimeError("GW2 tracker requires python 3.10+")

import argparse
import logging
from pathlib import Path

from gw2_tracker import app, utils

CONFIG: utils.SimpleNamespace[Path] = utils.SimpleNamespace(
    base=(base := Path("./gw2_tracker_data")),
    config=base / "config.json",
    model=base / "model.json",
    cache=base / "cache",
)


def main():
    parser = argparse.ArgumentParser(usage="GW2 resource tracker")
    parser.add_argument(
        "-d", "--debug", action="store_true", help="activate debug logging"
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    instance = app.GW2Tracker(model_file=CONFIG.model, cache_dir=CONFIG.cache)
    instance.start()


if __name__ == "__main__":
    main()
