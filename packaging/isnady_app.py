"""Entry point of the desktop applications (exe, AppImage, macOS app): the isnady window."""

import sys

from isnady.main import gui_main

if __name__ == "__main__":
    sys.exit(gui_main())
