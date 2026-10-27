"""PyInstaller entry point for SoulsOverlay.exe."""

import sys

from soulsoverlay.__main__ import frozen_main

if __name__ == "__main__":
    sys.exit(frozen_main())
