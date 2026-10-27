"""Edit → Preferences: reading text per script, theme colours and the interface font.

Every change is saved at once (isnady.config, shared with `iy config`) and the
window redraws; nothing needs an Apply button. Each row has its own Default
button and the dialog can reset everything.
"""

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from isnady import config
from isnady.gui import theme
from isnady.core.i18n import tr


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
        self.setText(value.upper() if value else tr("Default") + f"  {fallback.upper()}")
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
    button = QPushButton(tr("Default"))
    button.setObjectName("Quiet")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class PreferencesDialog(QDialog):
    changed = Signal()          # the main window redraws on this

    data_imported = Signal()   # a source was imported or removed; the main window refreshes its pages
    languages_changed = Signal()   # the languages of the texts chosen here; the pages draw their texts again
    sidebar_changed = Signal()     # the order of the sidebar's sections changed; the main window reorders them

    def __init__(self, parent=None, start_tab: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Preferences"))
        # room for the Data sources page (Bayram, 2026-10-24: "pencereyi genisletmemiz gerekiyor"): most of the screen
        screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if screen is not None:
            self.resize(min(1400, int(screen.width() * 0.85)), min(950, int(screen.height() * 0.88)))
        else:
            self.resize(1300, 880)
        self._rows = []           # callables that refresh a row from the settings

        from isnady.gui.sources_page import SourcesPage

        self.sources = SourcesPage()
        self.sources.data_imported.connect(self.data_imported)
        tabs = QTabWidget()
        tabs.addTab(self._scroll(self._themes_tab()), tr("Themes"))
        tabs.addTab(self._scroll(self._reading_tab()), tr("Reading text"))
        tabs.addTab(self._scroll(self._colors_tab()), tr("Colours"))
        tabs.addTab(self._scroll(self._interface_tab()), tr("Interface"))
        tabs.addTab(self._scroll(self._sidebar_tab()), tr("Sidebar"))
        tabs.addTab(self._scroll(self._books_tab()), tr("Books and languages"))
        tabs.addTab(self._scroll(self.sources), tr("Data sources"))
        tabs.addTab(self._scroll(self._reset_tab()), tr("Reset"))
        if start_tab == "sources":
            tabs.setCurrentIndex(tabs.count() - 2)
        elif start_tab == "books":
            tabs.setCurrentIndex(5)
        elif start_tab == "reset":
            tabs.setCurrentIndex(tabs.count() - 1)
        elif start_tab == "themes":
            tabs.setCurrentIndex(0)
        elif start_tab == "sidebar":
            tabs.setCurrentIndex(4)

        reset_all = QPushButton(tr("Reset appearance"))
        reset_all.setObjectName("Quiet")
        reset_all.clicked.connect(self._reset_all)
        close = QPushButton(tr("Close"))
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        self._close = close
        where = QLabel(tr("Saved in {settings_path}  ·  also:  iy config list", settings_path=config.settings_path()))
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

    # ------------------------------------------------------------ reset (RST1)
    def _reset_tab(self) -> QWidget:
        """Back to zero: the settings, the books, or everything of this profile (core.reset; `iy reset`)."""
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(12)
        intro = QLabel(tr("Bring isnady back to how it was: its settings, its books, or everything. Each asks once "
                          "more before it deletes; nothing can be undone."))
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        box.addWidget(intro)
        # each card says plainly what goes and what stays, so that the three are not alike (Bayram, 2026-10-24:
        # "hicbirsey anlamadim reset kisminda, sanki birbirinin ayni")
        t = theme.current()
        cards = (
            ("settings", tr("1. Only the settings"), tr("Delete the settings"), t.lapis,
             [tr("theme, fonts and colours"), tr("interface and content languages"), tr("the order of the sidebar"),
              tr("where you were in each book"), tr("recent searches")],
             [tr("the books"), tr("the bookmarks"), tr("the profiles")]),
            ("books", tr("2. Only the books"), tr("Delete the books"), t.gold,
             [tr("every hadith book"), tr("the rijal works and their narrators"), tr("your own sources"),
              tr("the search index and everything computed from them")],
             [tr("the settings"), tr("the bookmarks"), tr("the profiles")]),
            ("everything", tr("3. Everything"), tr("Delete everything"), "#B3261E",
             [tr("the books"), tr("the settings"), tr("the bookmarks"), tr("the downloaded copies of the data")],
             [tr("the other profiles")]))
        for kind, heading, title, color, goes, stays in cards:
            card = QFrame()
            card.setObjectName("Card")
            inner = QVBoxLayout(card)
            inner.setContentsMargins(18, 14, 18, 14)
            inner.setSpacing(8)
            head = QLabel(f"<span style='color:{color}; font-size:13pt; font-weight:700'>{heading}</span>")
            head.setTextFormat(Qt.TextFormat.RichText)
            inner.addWidget(head)
            cols = QHBoxLayout()
            for caption, items, mark in ((tr("Deleted"), goes, "✕"), (tr("Kept"), stays, "✓")):
                lines = "<br>".join(f"{mark}&nbsp; {i}" for i in items)
                block = QLabel(f"<b>{caption}</b><br>{lines}")
                block.setTextFormat(Qt.TextFormat.RichText)
                block.setAlignment(Qt.AlignmentFlag.AlignTop)
                cols.addWidget(block, 1)
            inner.addLayout(cols)
            button = QPushButton(title)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(f"QPushButton {{ color: white; background: {color}; border: none; border-radius: 6px; "
                                 f"padding: 6px 16px; font-weight: 600; }}")
            button.clicked.connect(lambda _c=False, k=kind, ti=title: self._reset(k, ti))
            row = QHBoxLayout()
            row.addWidget(button)
            row.addStretch(1)
            inner.addLayout(row)
            box.addWidget(card)
        box.addStretch(1)
        return page

    def _reset(self, kind: str, title: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        from isnady.core import reset

        what = {"settings": tr("All settings will be deleted; the books and bookmarks stay."),
                "books": tr("All books will be deleted; the settings and bookmarks stay."),
                "everything": tr("The books, the settings and the bookmarks will all be deleted.")}[kind]
        sure = QMessageBox.warning(self, title, what + "\n\n" + tr("This cannot be undone. Go on?"),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        if sure != QMessageBox.StandardButton.Yes:
            return
        if kind == "settings":
            n = reset.settings()
            done = tr("{n} settings deleted; isnady is as at its first start.", n=n)
        else:
            from isnady.data import db

            conn = db.connect()
            try:
                result = reset.books(conn) if kind == "books" else reset.everything(conn)
            finally:
                conn.close()
            n = result if kind == "books" else result["books"]
            done = (tr("{n} sources deleted.", n=n) if kind == "books"
                    else tr("Everything deleted ({n} sources, the settings and the bookmarks).", n=n))
            self.data_imported.emit()
        if kind != "books":
            self._refresh()
            self.changed.emit()
            self.languages_changed.emit()
            self.sidebar_changed.emit()
        QMessageBox.information(self, title, done)

    # ------------------------------------------------------------ plumbing
    @staticmethod
    def _scroll(widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(widget)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)   # the pages wrap; never scroll sideways
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
        self.sidebar_changed.emit()
        self._refresh()

    # ------------------------------------------------------------ themes (UI5)
    def _themes_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(14)
        intro = QLabel(tr("Choose how isnady looks. The change shows at once; View → Theme offers the same list."))
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        box.addWidget(intro)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        tiles = [("system", tr("Follow system"), tr("Sky by day, Starry Night by night — as the system is set"),
                  theme.SKY, theme.STARRY)]
        tiles += [(k, tr(name), tr(text), tokens, None) for k, (name, text, tokens) in theme.THEMES.items()]
        for n, (key, name, text, tokens, second) in enumerate(tiles):
            tile = ThemeTile(key, name, text, tokens, second)
            tile.clicked.connect(lambda _c=False, k=key: self._set("view.theme", k))
            grid.addWidget(tile, n // 3, n % 3)
            self._rows.append(lambda tile=tile: tile.setChecked(theme.theme_mode() == tile.key))
        box.addLayout(grid)
        note = QLabel(tr("Colours of your own (the Colours tab) apply to Lapis and Lapis Night."))
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
        intro = QLabel(tr("Each script has its own font, size, colour and line spacing. A text uses the settings of the "
                         "script its language is written in. View → Reading Text Size (Ctrl + / Ctrl −) scales them all "
                         "together."))
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
        title = QLabel(tr(label))
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
        color = ColorButton(tr("{script}: text colour", script=tr(label)))
        reset = _default_button()
        preview = QLabel(sample)
        preview.setObjectName("Preview")
        preview.setWordWrap(True)
        rtl = script == "arabic"
        preview.setAlignment((Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
                             | Qt.AlignmentFlag.AlignAbsolute)

        for col, (text, widget) in enumerate(((tr("Font"), family), (tr("Size"), size), (tr("Line spacing"), line),
                                             (tr("Colour"), color))):
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
        intro = QLabel(tr("The light and the dark theme keep their own colours. Choose which one to edit; the window shows "
                         "the theme picked in View → Theme."))
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        which = QComboBox()
        which.addItem(tr("Light theme"), "light")
        which.addItem(tr("Dark theme"), "dark")
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
            label = tr(label)
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
    def _books_tab(self) -> QWidget:
        """Which imported books are active (searched, listed, measured), and which languages the texts are shown
        in — the others folded behind an arrow on each hadith, or left out."""
        from PySide6.QtWidgets import QCheckBox, QRadioButton

        from isnady.core import books as core_books
        from isnady.core import language
        from isnady.core import search as core_search
        from isnady.data import db
        from isnady.gui.widgets import FlowLayout

        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(12)
        conn = db.connect()
        try:
            groups = core_books.grouped(conn, include_inactive=True)
            available = core_search.list_languages(conn)
        finally:
            conn.close()

        # ---- books
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        title = QLabel(tr("Books"))
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(13.5, bold=True))
        lay.addWidget(title)
        lead = QLabel(tr("A book switched off stays in the database but is left out of searches, book lists and statistics "
                        "until you switch it on again. To choose a few books for one search, use Books on the Search page."))
        lead.setObjectName("Caption")
        lead.setWordWrap(True)
        lay.addWidget(lead)
        checks: dict[str, QCheckBox] = {}
        if not groups:
            none = QLabel(tr("No books imported yet: Data sources."))
            none.setObjectName("Caption")
            lay.addWidget(none)
        for _t, label, group in groups:
            head = QHBoxLayout()
            g = QLabel(tr("{group} collections", group=tr(label)))
            g.setObjectName("FilterTitle")
            head.addWidget(g)
            head.addStretch(1)
            for text, on in ((tr("All on"), True), (tr("All off"), False)):
                b = QPushButton(text)
                b.setObjectName("Quiet")
                b.clicked.connect(lambda _c=False, grp=group, v=on: set_group(grp, v))
                head.addWidget(b)
            lay.addLayout(head)
            holder = QWidget()
            flow = FlowLayout(holder, spacing=10)
            for b in group:
                c = QCheckBox(f"{b['name']} ({b['count']:,})")
                c.setChecked(b["active"])
                c.toggled.connect(lambda on, k=b["key"]: toggle(k, on))
                flow.addWidget(c)
                checks[b["key"]] = c
            lay.addWidget(holder)
        box.addWidget(card)

        def toggle(key: str, on: bool) -> None:
            core_books.set_active(key, on)
            self.data_imported.emit()

        def set_group(group: list, on: bool) -> None:
            for b in group:
                c = checks[b["key"]]
                c.blockSignals(True)
                c.setChecked(on)
                c.blockSignals(False)
                core_books.set_active(b["key"], on)
            self.data_imported.emit()

        # ---- languages
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        title = QLabel(tr("Languages of the texts"))
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(13.5, bold=True))
        lay.addWidget(title)
        lead = QLabel(tr("The languages each hadith is shown in, in this order: Arabic always first, the others as you "
                        "put them — drag a language to its place or move it with the arrows. A text that matches your "
                        "search is always shown. The same as Content in the sidebar."))
        lead.setObjectName("Caption")
        lead.setWordWrap(True)
        lay.addWidget(lead)
        # the order of the languages after Arabic (Bayram, 2026-10-24: "Dilleri (Arapca disinda) yerlerini
        # duzenleyebilmemiz lazim"): a list to tick and to drag, Arabic fixed at its head
        chosen = language.content_languages()
        lang_row = QHBoxLayout()
        lang_row.setSpacing(14)
        listing = QListWidget()
        listing.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        listing.setDefaultDropAction(Qt.DropAction.MoveAction)
        listing.setFixedHeight(min(12, max(3, len(available))) * 32 + 8)
        listing.setMaximumWidth(420)
        lang_row.addWidget(listing, 1)
        lang_buttons = QVBoxLayout()
        lang_buttons.setSpacing(8)
        up = QPushButton("▲  " + tr("Move up"))
        down = QPushButton("▼  " + tr("Move down"))
        az = _default_button()
        az.setToolTip(tr("Arabic first, the others from A to Z"))
        for b in (up, down, az):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lang_buttons.addWidget(b)
        lang_buttons.addStretch(1)
        lang_row.addLayout(lang_buttons)
        lang_row.addStretch(1)
        lay.addLayout(lang_row)

        def fill_languages() -> None:
            current = listing.currentItem().data(Qt.ItemDataRole.UserRole) if listing.currentItem() else None
            picked = language.content_languages()
            listing.blockSignals(True)
            listing.clear()
            for i, lang in enumerate(language.sort(available)):
                arabic = lang == "Arabic"
                item = QListWidgetItem(f"{i + 1}.  {tr(lang)}" + ("   — " + tr("always first") if arabic else ""))
                item.setData(Qt.ItemDataRole.UserRole, lang)
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable
                if not arabic:
                    flags |= Qt.ItemFlag.ItemIsDragEnabled
                item.setFlags(flags)
                item.setCheckState(Qt.CheckState.Checked if not picked or lang in picked else Qt.CheckState.Unchecked)
                item.setSizeHint(QSize(0, 32))
                listing.addItem(item)
                if lang == current:
                    listing.setCurrentItem(item)
            listing.blockSignals(False)

        def save_order() -> None:
            langs = [listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count())]
            others = [lang for lang in langs if lang != "Arabic"]
            language.set_order([] if others == sorted(others) else others)
            fill_languages()
            self.languages_changed.emit()

        def move_language(step: int) -> None:
            i = listing.currentRow()
            j = i + step
            if i < 0 or not 0 <= j < listing.count():
                return
            if "Arabic" in (listing.item(i).data(Qt.ItemDataRole.UserRole), listing.item(j).data(Qt.ItemDataRole.UserRole)):
                return                                  # Arabic stays at the head
            item = listing.takeItem(i)
            listing.insertItem(j, item)
            listing.setCurrentRow(j)
            save_order()

        def save_languages() -> None:
            items = [listing.item(i) for i in range(listing.count())]
            picked = [it.data(Qt.ItemDataRole.UserRole) for it in items if it.checkState() == Qt.CheckState.Checked]
            language.set_content_languages([] if not picked or len(picked) == len(items) else picked)
            self.languages_changed.emit()

        fill_languages()
        listing.itemChanged.connect(lambda _item: save_languages())
        # after the drop has finished; a language dropped above Arabic goes back below it (language.sort)
        listing.model().rowsMoved.connect(lambda *_a: QTimer.singleShot(0, save_order))
        up.clicked.connect(lambda: move_language(-1))
        down.clicked.connect(lambda: move_language(+1))
        az.clicked.connect(lambda: (language.set_order([]), fill_languages(), self.languages_changed.emit()))
        self._rows.append(fill_languages)
        fold = QRadioButton(tr("Fold the other languages behind an arrow on each hadith (▸ click to open)"))
        omit = QRadioButton(tr("Leave the other languages out"))
        (fold if language.folds() else omit).setChecked(True)
        fold.toggled.connect(lambda on: (language.set_folds(on), self.languages_changed.emit()))
        lay.addWidget(fold)
        lay.addWidget(omit)
        box.addWidget(card)
        box.addStretch(1)

        return page

    def _sidebar_tab(self) -> QWidget:
        """The order of the sidebar's sections: dragged, or moved with the arrows; Default puts isnady's back."""
        from isnady.gui.main_window import SECTIONS

        labels = {k: tr(l) for k, l, _t in SECTIONS}
        texts = {k: tr(t) for k, _l, t in SECTIONS}
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(12)
        intro = QLabel(tr("The order of the sections in the sidebar. Drag a section to its place, or choose it and "
                          "move it with the arrows; Ctrl+1 … Ctrl+9 follow the order. The change shows at once."))
        intro.setObjectName("Lead")
        intro.setWordWrap(True)
        box.addWidget(intro)

        card = QFrame()
        card.setObjectName("Card")
        row = QHBoxLayout(card)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(14)
        listing = QListWidget()
        listing.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        listing.setDefaultDropAction(Qt.DropAction.MoveAction)
        listing.setFixedHeight(9 * 32 + 8)
        listing.setMaximumWidth(420)
        row.addWidget(listing, 1)
        buttons = QVBoxLayout()
        buttons.setSpacing(8)
        up = QPushButton("▲  " + tr("Move up"))
        down = QPushButton("▼  " + tr("Move down"))
        reset = _default_button()
        for b in (up, down, reset):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            buttons.addWidget(b)
        buttons.addStretch(1)
        row.addLayout(buttons)
        row.addStretch(1)
        box.addWidget(card)
        box.addStretch(1)

        def fill():
            current = listing.currentItem().data(Qt.ItemDataRole.UserRole) if listing.currentItem() else None
            listing.blockSignals(True)
            listing.clear()
            for i, key in enumerate(config.sidebar_order()):
                item = QListWidgetItem(f"{i + 1}.  {labels[key]}")
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setToolTip(texts[key])
                item.setSizeHint(QSize(0, 32))
                listing.addItem(item)
                if key == current:
                    listing.setCurrentItem(item)
            listing.blockSignals(False)

        def save():
            keys = [listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count())]
            try:
                config.set("view.sidebar", ",".join(keys))
            except config.ConfigError:
                return
            fill()
            self.sidebar_changed.emit()

        def move(step: int):
            i = listing.currentRow()
            j = i + step
            if i < 0 or not 0 <= j < listing.count():
                return
            item = listing.takeItem(i)
            listing.insertItem(j, item)
            listing.setCurrentRow(j)
            save()

        # after the drop has finished: the list is filled again (numbers) in save()
        listing.model().rowsMoved.connect(lambda *_a: QTimer.singleShot(0, save))
        up.clicked.connect(lambda: move(-1))
        down.clicked.connect(lambda: move(+1))
        reset.clicked.connect(lambda: (config.set("view.sidebar", ""), fill(), self.sidebar_changed.emit()))
        self._rows.append(fill)
        return page

    def _interface_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        box = QVBoxLayout(page)
        box.setContentsMargins(6, 12, 12, 12)
        box.setSpacing(12)
        intro = QLabel(tr("The font of menus, buttons and labels. Reading text has its own settings."))
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
        size.setSpecialValueText(tr("System size"))
        size.setSuffix(" pt")
        reset = _default_button()
        theme_combo = QComboBox()
        for mode, label in (("system", tr("Follow system")), ("light", tr("Light")), ("dark", tr("Dark"))):
            theme_combo.addItem(label, mode)
        for row, (text, widget) in enumerate(((tr("Font"), family), (tr("Size"), size), (tr("Theme"), theme_combo))):
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
