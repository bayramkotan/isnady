"""Entry points.

The same program answers to several names:
  isnady, iy      no arguments: open the window; with arguments: the command line
  isnady-gui      always the window, without a console on Windows
  isnady-cli      the command line (kept from the first releases)

The command line never imports Qt, so it works on a server, over SSH and in
scripts, and starts quickly.
"""

import sys

from isnady import APP_NAME, __version__


def gui_main() -> int:
    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("The isnady window needs PySide6:  pip install PySide6\n"
              "The command line works without it; see:  iy -h", file=sys.stderr)
        return 1

    from isnady.gui import theme
    from isnady.gui.main_window import MainWindow

    import os

    from PySide6.QtCore import QLoggingCategory

    if not os.environ.get("QT_LOGGING_RULES"):
        # Qt reports, for EVERY installed font, that it cannot shape a script none of them covers (Bengali,
        # Tamil, … — "OpenType support missing for …, script 12"): hundreds of harmless lines. Only that
        # category is silenced; every other Qt warning still shows. A user's own QT_LOGGING_RULES wins.
        QLoggingCategory.setFilterRules("qt.text.font.db=false")
    app = QApplication(sys.argv[:1])
    from importlib import resources

    from PySide6.QtGui import QIcon

    icon = resources.files("isnady") / "assets" / "icons" / "isnady.png"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))        # the window, the taskbar and the dock
    app.setApplicationName("isnady")
    app.setDesktopFileName("isnady")
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    theme.load_fonts()
    theme.migrate_qsettings()
    theme.apply(app)
    window = MainWindow()

    hints = QGuiApplication.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        def _follow_scheme(*_args):
            if theme.theme_mode() == "system":
                theme.apply(app)
                window.retheme()
        hints.colorSchemeChanged.connect(_follow_scheme)

    window.show()
    window.check_installation_later()
    return app.exec()


def main() -> int:
    """No arguments: the window. Any argument: the command line."""
    if len(sys.argv) > 1:
        from isnady.cli import main as cli_main

        return cli_main(sys.argv[1:])
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
