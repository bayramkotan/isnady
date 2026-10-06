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


class ThemeTile(QPushButton):
    """A theme drawn as a small isnady window: sidebar with the wordmark, a search field, a card, the accent."""

    def __init__(self, key: str, name: str, text: str, tokens, second=None) -> None:
        super().__init__()
        self.key, self.name, self.text_, self.t, self.second = key, name, text, tokens, second
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(text)
        self.setFixedSize(236, 196)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def _window(self, p, rect, t) -> None:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QPainterPath

        clip = QPainterPath()
        clip.addRoundedRect(rect, 10, 10)
        p.save()
        p.setClipPath(clip, Qt.ClipOperation.IntersectClip)   # keep an outer clip (the halves of "Follow system")
        p.fillRect(rect, QColor(t.window))
        side = QRectF(rect.left(), rect.top(), rect.width() * 0.28, rect.height())
        p.fillRect(side, QColor(t.sidebar))
        p.setPen(QColor(t.sidebar_ink))
        f = p.font()
        f.setPointSizeF(7.5)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(side.left() + 7, side.top() + 6, side.width(), 14), "isnady")
        for i in range(4):
            y = side.top() + 30 + i * 14
            colour = QColor(t.sidebar_selected) if i == 0 else QColor(t.sidebar_muted)
            if i == 0:
                p.fillRect(QRectF(side.left() + 4, y - 2, side.width() - 8, 11), colour)
                p.fillRect(QRectF(side.left() + 4, y - 2, 2, 11), QColor(t.gold))
            else:
                p.fillRect(QRectF(side.left() + 9, y + 2, side.width() * 0.5, 3), colour)
        main = QRectF(side.right() + 8, rect.top() + 8, rect.right() - side.right() - 16, rect.height() - 16)
        p.setPen(QColor(t.border))
        p.setBrush(QColor(t.surface))
        p.drawRoundedRect(QRectF(main.left(), main.top(), main.width() * 0.74, 14), 5, 5)
        p.setBrush(QColor(t.lapis))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(main.left() + main.width() * 0.78, main.top(), main.width() * 0.22, 14), 5, 5)
        card = QRectF(main.left(), main.top() + 22, main.width(), main.height() - 22)
        p.setPen(QColor(t.border))
        p.setBrush(QColor(t.surface))
        p.drawRoundedRect(card, 7, 7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.ink))
        p.drawRoundedRect(QRectF(card.left() + 8, card.top() + 8, card.width() * 0.4, 5), 2, 2)
        p.setBrush(QColor(t.pill))
        p.drawRoundedRect(QRectF(card.left() + 8, card.top() + 18, card.width() * 0.3, 7), 3, 3)
        p.setBrush(QColor(t.muted))
        for i in range(3):
            p.drawRoundedRect(QRectF(card.left() + 8 + (0 if i else card.width() * 0.2), card.top() + 32 + i * 9,
                                     card.width() * (0.8 if i else 0.6), 3), 1.5, 1.5)
        p.fillRect(QRectF(card.left() + 8, card.top() + 62, 2, 20), QColor(t.gold))
        p.setBrush(QColor(t.gilt))
        p.drawRoundedRect(QRectF(card.left() + 14, card.top() + 63, card.width() * 0.22, 6), 2, 2)
        p.restore()

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QPainter, QPen

        cur = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(2, 2, self.width() - 4, 136)
        if self.second is None:
            self._window(p, frame, self.t)
        else:                                       # "Follow system": light and dark, halves
            half = QRectF(frame.left(), frame.top(), frame.width() / 2, frame.height())
            p.save()
            p.setClipRect(half)
            self._window(p, frame, self.t)
            p.restore()
            p.save()
            p.setClipRect(QRectF(half.right(), frame.top(), frame.width() / 2, frame.height()))
            self._window(p, frame, self.second)
            p.restore()
        ring = QColor(cur.lapis) if self.isChecked() else (QColor(cur.muted) if self.underMouse() else QColor(cur.border))
        p.setPen(QPen(ring, 3 if self.isChecked() else 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(frame, 10, 10)
        p.setPen(QColor(cur.ink))
        f = self.font()
        f.setBold(True)
        f.setPointSizeF(max(f.pointSizeF(), 9.5) + 0.5)
        p.setFont(f)
        p.drawText(QRectF(4, 144, self.width() - 8, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   ("✓  " if self.isChecked() else "") + self.name)
        f.setBold(False)
        f.setPointSizeF(f.pointSizeF() - 1.5)
        p.setFont(f)
        p.setPen(QColor(cur.muted))
        p.drawText(QRectF(4, 164, self.width() - 8, 30), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.text_)
        p.end()


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
        tabs.addTab(self._scroll(self._themes_tab()), "Themes")
        tabs.addTab(self._scroll(self._reading_tab()), "Reading text")
        tabs.addTab(self._scroll(self._colors_tab()), "Colours")
        tabs.addTab(self._scroll(self._interface_tab()), "Interface")
        tabs.addTab(self._scroll(self.sources), "Data sources")
        if start_tab == "sources":
            tabs.setCurrentIndex(tabs.count() - 1)
        elif start_tab == "themes":
            tabs.setCurrentIndex(0)

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

    # ------------------------------------------------------------ themes (UI5)
    def _themes_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(14)
        intro = QLabel("Choose how isnady looks. The change shows at once; View → Theme offers the same list.")
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        box.addWidget(intro)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        tiles = [("system", "Follow system", "Lapis by day, Lapis Night by night — as the system is set",
                  theme.LIGHT, theme.DARK)]
        tiles += [(k, name, text, tokens, None) for k, (name, text, tokens) in theme.THEMES.items()]
        for n, (key, name, text, tokens, second) in enumerate(tiles):
            tile = ThemeTile(key, name, text, tokens, second)
            tile.clicked.connect(lambda _c=False, k=key: self._set("view.theme", k))
            grid.addWidget(tile, n // 3, n % 3)
            self._rows.append(lambda tile=tile: tile.setChecked(theme.theme_mode() == tile.key))
        box.addLayout(grid)
        note = QLabel("Colours of your own (the Colours tab) apply to Lapis and Lapis Night.")
        note.setObjectName("Caption")
        box.addWidget(note)
        box.addStretch(1)
        return page

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
