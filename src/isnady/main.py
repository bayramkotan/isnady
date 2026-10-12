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
    if sys.platform == "win32":
        # without its own id, Windows groups the window under python(w).exe and shows Python's icon in the taskbar
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("bayramkotan.isnady")
        except (AttributeError, OSError):
            pass
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
    from PySide6.QtCore import Qt

    from isnady.core import i18n, language

    def _speak() -> None:
        """The interface language (I1): the texts, and right to left for Arabic, Persian, Dari, Pashto, Urdu."""
        i18n.set_language(language.ui_language())
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.rtl() else Qt.LayoutDirection.LeftToRight)

    _speak()
    windows: list = []

    def _open(old=None) -> None:
        window = MainWindow()
        window.language_switched.connect(_switch)
        if old is not None:
            window.setGeometry(old.geometry())
            window.nav.setCurrentRow(old.nav.currentRow())
            if old.isMaximized():
                window.showMaximized()
        windows.append(window)
        window.show()

    def _switch() -> None:
        """Another interface language: the window is built again in it, where the reader was."""
        old = windows.pop()
        _speak()
        _open(old)
        old.hide()
        old.deleteLater()

    _open()

    hints = QGuiApplication.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        def _follow_scheme(*_args):
            if theme.theme_mode() == "system":
                theme.apply(app)
                windows[-1].retheme()
        hints.colorSchemeChanged.connect(_follow_scheme)

    windows[-1].check_installation_later()
    code = app.exec()
    # an import still running after the window closed would keep the process (and the database's write lock) alive
    # in the background: the next start found "database is locked". End at once; SQLite rolls the unfinished book
    # back on the next open (WAL), the books already imported stay.
    from isnady.gui import sources_page

    if any(w.isRunning() for w in sources_page._LIVE_WORKERS):
        os._exit(code)
    return code


def main() -> int:
    """No arguments: the window. Any argument: the command line."""
    if len(sys.argv) > 1:
        from isnady.cli import main as cli_main

        return cli_main(sys.argv[1:])
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
