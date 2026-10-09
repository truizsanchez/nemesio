"""The suite runs with no window and no cartridge.

No cartridge ships with this repository, so none is read here: the tests build
cartridge-shaped bytes in a few lines and check the readers' rules on them.
Whether the readers give the original's own graphics and maps, byte for byte,
is checked against the real cartridge running in openMSX by `tools/check_rom.py`.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
