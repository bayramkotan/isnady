"""Edit → Preferences: reading text per script, theme colours and the interface font.

Every change is saved at once (isnady.config, shared with `iy config`) and the
window redraws; nothing needs an Apply button. Each row has its own Default
button and the dialog can reset everything.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from isnady import config
from isnady.gui import theme


class ColorButton(QPushButton):
    """Shows a colour; click to choose, the Default button next to it clears it."""

    picked = Signal(str)

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title
        self._value = ""
        self._fallback = "#000000"
        self.setObjectName("Swatch")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(130)
        self.clicked.connect(self._choose)

    def set_value(self, value: str, fallback: str) -> None:
        self._value, self._fallback = value, fallback
        shown = value or fallback
        ink = "#000000" if QColor(shown).lightness() > 140 else "#FFFFFF"
        self.setText(value.upper() if value else f"Default  {fallback.upper()}")
        self.setStyleSheet(f"QPushButton#Swatch {{ background: {shown}; color: {ink}; border-radius: 6px;"
                           f" padding: 5px 10px; border: 1px solid {theme.current().border}; }}")

    def _choose(self) -> None:
        color = QColorDialog.getColor(QColor(self._value or self._fallback), self, self._title)
        if color.isValid():
            self.picked.emit(color.name().upper())


def _default_button() -> QPushButton:
    button = QPushButton("Default")
    button.setObjectName("Quiet")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class PreferencesDialog(QDialog):
    changed = Signal()          # the main window redraws on this

    data_imported = Signal()   # a source was imported or removed; the main window refreshes its pages

    def __init__(self, parent=None, start_tab: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(900, 700)
        self._rows = []           # callables that refresh a row from the settings

        from isnady.gui.sources_page import SourcesPage

        self.sources = SourcesPage()
        self.sources.data_imported.connect(self.data_imported)
        tabs = QTabWidget()
        tabs.addTab(self._scroll(self._reading_tab()), "Reading text")
        tabs.addTab(self._scroll(self._colors_tab()), "Colours")
        tabs.addTab(self._scroll(self._interface_tab()), "Interface")
        tabs.addTab(self._scroll(self.sources), "Data sources")
        if start_tab == "sources":
            tabs.setCurrentIndex(tabs.count() - 1)

        reset_all = QPushButton("Reset appearance")
        reset_all.setObjectName("Quiet")
        reset_all.clicked.connect(self._reset_all)
        close = QPushButton("Close")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        self._close = close
        where = QLabel(f"Saved in {config.settings_path()}  ·  also:  iy config list")
        where.setObjectName("Caption")
        where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        bottom = QHBoxLayout()
        bottom.addWidget(where, 1)
        bottom.addWidget(reset_all)
        bottom.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.addWidget(tabs, 1)
        layout.addLayout(bottom)
        self._refresh()

    # ------------------------------------------------------------ plumbing
    @staticmethod
    def _scroll(widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(widget)
        return area

    def _set(self, key: str, value) -> None:
        try:
            config.set(key, value)
        except config.ConfigError:
            return
        self.changed.emit()
        self._refresh()

    def reject(self) -> None:          # Escape / window close
        if self.sources.busy():
            return                     # an import is running; its own thread finishes it
        super().reject()

    def accept(self) -> None:
        if self.sources.busy():
            return
        super().accept()

    def _refresh(self) -> None:
        for refresh in self._rows:
            refresh()

    def _reset_all(self) -> None:
        config.reset()
        self.changed.emit()
        self._refresh()

    # ------------------------------------------------------------ reading text
    def _reading_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(14)
        intro = QLabel("Each script has its own font, size, colour and line spacing. A text uses the settings of "
                       "the script its language is written in. View → Reading Text Size (Ctrl + / Ctrl −) "
                       "scales them all together.")
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        box.addWidget(intro)
        for script, (label, sample, _family, _size, _line) in config.SCRIPTS.items():
            box.addWidget(self._script_card(script, label, sample))
        box.addStretch(1)
        return page

    def _script_card(self, script: str, label: str, sample: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 14, 18, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        title = QLabel(label)
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(14, bold=True))
        grid.addWidget(title, 0, 0, 1, 6)

        family = QFontComboBox()
        size = QDoubleSpinBox()
        size.setRange(6, 48)
        size.setSingleStep(0.5)
        size.setSuffix(" pt")
        line = QSpinBox()
        line.setRange(80, 250)
        line.setSingleStep(5)
        line.setSuffix(" %")
        color = ColorButton(f"{label}: text colour")
        reset = _default_button()
        preview = QLabel(sample)
        preview.setObjectName("Preview")
        preview.setWordWrap(True)
        rtl = script == "arabic"
        preview.setAlignment((Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
                             | Qt.AlignmentFlag.AlignAbsolute)

        for col, (text, widget) in enumerate((("Font", family), ("Size", size), ("Line spacing", line),
                                             ("Colour", color))):
            caption = QLabel(text)
            caption.setObjectName("FilterLabel")
            grid.addWidget(caption, 1, col)
            grid.addWidget(widget, 2, col)
        grid.addWidget(reset, 2, 5)
        grid.addWidget(preview, 3, 0, 1, 6)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(4, 0)

        def refresh():
            for w in (family, size, line):
                w.blockSignals(True)
            fam = config.get(f"text.{script}.family")
            family.setCurrentFont(QFont(fam) if fam else QFont(self.font()))
            size.setValue(float(config.get(f"text.{script}.size")))
            line.setValue(int(config.get(f"text.{script}.line_height")))
            for w in (family, size, line):
                w.blockSignals(False)
            color.set_value(config.get(f"text.{script}.color"), theme.current().ink)
            preview.setStyleSheet(f"color: {theme.script_color(script)}; padding-top: 6px; "
                                  f"{theme.font_css(theme.script_font(script))}")

        family.currentFontChanged.connect(lambda f: self._set(f"text.{script}.family", f.family()))
        size.valueChanged.connect(lambda v: self._set(f"text.{script}.size", v))
        line.valueChanged.connect(lambda v: self._set(f"text.{script}.line_height", v))
        color.picked.connect(lambda v: self._set(f"text.{script}.color", v))
        reset.clicked.connect(lambda: (config.reset(f"text.{script}"), self.changed.emit(), self._refresh()))
        self._rows.append(refresh)
        return card

    # ------------------------------------------------------------ colours
    def _colors_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(12)
        intro = QLabel("The light and the dark theme keep their own colours. Choose which one to edit; the "
                       "window shows the theme picked in View → Theme.")
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        which = QComboBox()
        which.addItem("Light theme", "light")
        which.addItem("Dark theme", "dark")
        which.setCurrentIndex(1 if theme.current().dark else 0)
        head = QHBoxLayout()
        head.addWidget(which)
        head.addStretch(1)
        box.addWidget(intro)
        box.addLayout(head)

        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 14, 18, 14)
        grid.setVerticalSpacing(8)
        base = {"light": theme.LIGHT, "dark": theme.DARK}
        for row, (token, label) in enumerate(config.COLOR_TOKENS.items()):
            name = QLabel(label)
            button = ColorButton(label)
            reset = _default_button()
            grid.addWidget(name, row, 0)
            grid.addWidget(button, row, 1)
            grid.addWidget(reset, row, 2)

            def refresh(token=token, button=button):
                mode = which.currentData()
                button.set_value(config.get(f"colors.{mode}.{token}"), getattr(base[mode], token))

            button.picked.connect(lambda v, token=token: self._set(f"colors.{which.currentData()}.{token}", v))
            reset.clicked.connect(lambda _c=False, token=token: self._set(f"colors.{which.currentData()}.{token}", ""))
            self._rows.append(refresh)
        grid.setColumnStretch(0, 1)
        which.currentIndexChanged.connect(lambda _i: self._refresh())
        box.addWidget(card)
        box.addStretch(1)
        return page

    # ------------------------------------------------------------ interface
    def _interface_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(12)
        intro = QLabel("The font of menus, buttons and labels. Reading text has its own settings.")
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        box.addWidget(intro)

        card = QFrame()
        card.setObjectName("Card")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 14, 18, 14)
        family = QFontComboBox()
        size = QDoubleSpinBox()
        size.setRange(0, 24)
        size.setSingleStep(0.5)
        size.setSpecialValueText("System size")
        size.setSuffix(" pt")
        reset = _default_button()
        theme_combo = QComboBox()
        for mode, label in (("system", "Follow system"), ("light", "Light"), ("dark", "Dark")):
            theme_combo.addItem(label, mode)
        for row, (text, widget) in enumerate((("Font", family), ("Size", size), ("Theme", theme_combo))):
            caption = QLabel(text)
            caption.setObjectName("FilterLabel")
            grid.addWidget(caption, row, 0)
            grid.addWidget(widget, row, 1)
        grid.addWidget(reset, 0, 2)
        grid.setColumnStretch(1, 1)
        box.addWidget(card)
        box.addStretch(1)

        def refresh():
            for w in (family, size, theme_combo):
                w.blockSignals(True)
            fam = config.get("ui.family")
            family.setCurrentFont(QFont(fam) if fam else self.font())
            size.setValue(float(config.get("ui.size")))
            theme_combo.setCurrentIndex(max(theme_combo.findData(config.get("view.theme")), 0))
            for w in (family, size, theme_combo):
                w.blockSignals(False)

        family.currentFontChanged.connect(lambda f: self._set("ui.family", f.family()))
        size.valueChanged.connect(lambda v: self._set("ui.size", v if v else ""))
        theme_combo.currentIndexChanged.connect(lambda _i: self._set("view.theme", theme_combo.currentData()))
        reset.clicked.connect(lambda: (config.reset("ui"), self.changed.emit(), self._refresh()))
        self._rows.append(refresh)
        return page
