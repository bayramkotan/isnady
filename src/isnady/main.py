"""Entry point: `isnady` command and `python -m isnady`."""

import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from isnady import APP_NAME, __version__
from isnady.gui import theme
from isnady.gui.main_window import MainWindow


def main() -> int:
    if "--version" in sys.argv[1:]:
        print(f"{APP_NAME} {__version__}")
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    theme.load_fonts()
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
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
