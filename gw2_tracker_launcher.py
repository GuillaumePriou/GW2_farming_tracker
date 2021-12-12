#!/usr/bin/env python
"""
Laucher script for the GW2 tracker app.

This script makes it easier to have all pyinstaller-related files at the
top-level of the project
"""
import sys
if sys.version_info < (3, 10):
    raise RuntimeError("GW2 tracker requires python 3.10+")

import gw2_tracker.__main__
gw2_tracker.__main__.main()