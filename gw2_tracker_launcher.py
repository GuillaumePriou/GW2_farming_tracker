#!/usr/bin/env python
import sys
if sys.version_info < (3, 10):
    raise RuntimeError("GW2 tracker requires python 3.10+")

import gw2_tracker.__main__
gw2_tracker.__main__.main()