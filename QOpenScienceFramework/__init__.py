__version__ = "1.1.8"
__author__ = "Daniel Schreij"

import os
import sys
from QOpenScienceFramework.compat import *
dirname = safe_decode(os.path.dirname(__file__),
	enc=sys.getfilesystemencoding())

import QOpenScienceFramework.widgets
import QOpenScienceFramework.connection
import QOpenScienceFramework.manager

