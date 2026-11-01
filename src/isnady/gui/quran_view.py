"""The Qur'an in Books (Q1): a sura with its verses in Arabic and the translations chosen, a search through the whole
text, and under each verse the hadith that name it (Q2, GEN1-H2). Downloaded on request (core.quran)."""

import html

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from isnady.core import i18n
from isnady.core import quran as core
from isnady.core.i18n import tr
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout, TextBlock, WrapLabel

PAGE = 40                    # verses drawn at a time (al-Baqara has 286)


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    label = WrapLabel(text) if wrap else QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


_RUNNING: set = set()                # threads kept alive until they end, whatever window started them closes


def _keep(job: QThread) -> QThread:
    _RUNNING.add(job)
    job.finished.connect(lambda j=job: _RUNNING.discard(j))
    return job


class _Fetch(QThread):
    said = Signal(str)
    ended = Signal(str)                  # "" when done, else what went wrong

    def __init__(self, editions: list[str], info: dict | None = None) -> None:
        super().__init__()
        self._editions, self._info = editions, info
        self.kept: list[str] = []

    def run(self) -> None:
        try:
            self.kept = core.fetch(self._editions, self.said.emit, self._info)
            self.ended.emit("")
        except Exception as exc:  # noqa: BLE001 — said to the reader, the rest of isnady goes on
            core._log().exception("The Qur'an could not be downloaded")
            self.ended.emit(f"{type(exc).__name__}: {exc}")


class _Catalog(QThread):
    ready = Signal(object)

    def run(self) -> None:
        try:
            self.ready.emit(core.catalog())
        except Exception as exc:  # noqa: BLE001
            core._log().exception("The list of the Qur'an's translations could not be read")
            self.ready.emit(exc)


class AddTranslations(QDialog):
    """The translations there are, by language — isnady-data's first, then the source's; the ones ticked are
    downloaded, a downloaded one unticked is removed."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Translations of the Qur'an"))
        self.resize(660, 580)
        self.chosen: list[str] = []
        self.removed: list[str] = []
        self.info: dict = {}
        self._info: dict = {}
        self._have: set[str] = {e["key"] for e in core.editions()}
        self._ticks: dict[str, bool] = {}
        box = QVBoxLayout(self)
        box.addWidget(_label(tr("The translations isnady-data keeps come first (★); the others, of 98 languages, are "
                                "read from fawazahmed0/quran-api (each from Tanzil, the King Fahd Complex, QuranEnc or "
                                "another source it names). Tick a translation to download it (about 1 MB); untick one "
                                "downloaded to remove it."), "Caption"))
        self.language = QComboBox()
        self.language.currentIndexChanged.connect(lambda _i: self._fill())
        box.addWidget(self.language)
        self.list = QListWidget()
        self.list.itemChanged.connect(self._ticked)
        box.addWidget(self.list, 1)
        self.status = _label(tr("Reading the list of translations …"), "Caption")
        box.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.ok = buttons.addButton(tr("Apply"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.ok.setEnabled(False)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)
        self._job = _keep(_Catalog())
        self._job.ready.connect(self._loaded)
        self._job.start()

    def done(self, result: int) -> None:
        try:                                   # closed before the list came: the thread ends on its own
            self._job.ready.disconnect(self._loaded)
        except (RuntimeError, TypeError):
            pass
        super().done(result)

    def _loaded(self, info) -> None:
        if isinstance(info, Exception):
            self.status.setText(tr("The list could not be read: {error}", error=str(info)))
            return
        self._info = info
        langs = sorted({v["language"] for k, v in info.items() if not k.endswith("_la") and not k.endswith("-la")
                        and k != core.ARABIC},
                       key=lambda lang: (not any(v["origin"] == core.OWN for k, v in info.items()
                                                 if v["language"] == lang and k != core.ARABIC), tr(lang)))
        mine = {"tr": "Turkish", "en": "English", "ar": "English"}.get(i18n.language(), "English")
        self.language.blockSignals(True)
        for lang in langs:
            n = sum(1 for k, v in info.items() if v["language"] == lang and v["origin"] == core.OWN
                    and k != core.ARABIC)
            self.language.addItem(tr(lang) + (f"  ★{n}" if n else ""), lang)
        self.language.setCurrentIndex(max(0, self.language.findData(mine)))
        self.language.blockSignals(False)
        own = sum(1 for k, v in info.items() if v["origin"] == core.OWN and k != core.ARABIC)
        self.status.setText(tr("{n} translations in {languages} languages", n=len(info), languages=len(langs))
                            + (" · " + tr("{n} of them in isnady-data", n=own) if own else
                               " · " + tr("isnady-data has none yet: all are read from the source")))
        self.ok.setEnabled(True)
        self._fill()

    def _fill(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        lang = self.language.currentData()
        rows = [(k, v) for k, v in self._info.items()
                if v["language"] == lang and not k.endswith("-la") and k != core.ARABIC]
        rows.sort(key=lambda kv: (kv[1]["origin"] != core.OWN, kv[1]["author"].lower()))
        for key, v in rows:
            star = "★ " if v["origin"] == core.OWN else ""
            where = v.get("source") or v["origin"]
            note = f" — {v['comments']}" if v.get("comments") else ""
            have = key in self._have
            item = QListWidgetItem(f"{star}{v['author']}   ({where}){note}"
                                   + ("   ✓ " + tr("downloaded") if have else ""))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(tr("Read from {origin}", origin=v["origin"]) + (f"\n{v['url']}" if v.get("url") else ""))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            on = self._ticks.get(key, have)
            item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        if not rows:
            self.list.addItem(QListWidgetItem(tr("No translation in this language")))
        self.list.blockSignals(False)

    def _ticked(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self._ticks[key] = item.checkState() == Qt.CheckState.Checked

    def _accept(self) -> None:
        self.chosen = [k for k, on in self._ticks.items() if on and k not in self._have]
        self.removed = [k for k, on in self._ticks.items() if not on and k in self._have]
        self.info = self._info
        self.accept()


class QuranView(QWidget):
    open_hadith = Signal(int)            # a hadith that names a verse → in its book
    open_chain = Signal(int)
    downloaded = Signal()                # the text came: the contents (the suras) can be drawn

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._sura = 1
        self._focus: int | None = None
        self._shown = 0
        self._rows: list[dict] = []
        self._job = None
        self._conn_of = lambda: None

        self.title = _label("", "CardTitle", wrap=False)
        self.title.setFont(theme.reading_font(20, bold=True))
        self.arabic_title = QLabel("")
        self.arabic_title.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                                        f"{theme.font_css(theme.script_font('arabic', factor=0.9))}")
        self.facts = _label("", "Caption")
        self.prev = QPushButton("‹  " + tr("Previous sura"))
        self.next = QPushButton(tr("Next sura") + "  ›")
        for b in (self.prev, self.next):
            b.setObjectName("Quiet")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev.clicked.connect(lambda: self.show_sura(self._sura - 1))
        self.next.clicked.connect(lambda: self.show_sura(self._sura + 1))
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("Search the Qur'an — Arabic or a translation's words"))
        self.find.setClearButtonEnabled(True)
        self.find.returnPressed.connect(self._search)
        self.add = QPushButton("➕ " + tr("Translations…"))
        self.add.setObjectName("Quiet")
        self.add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add.clicked.connect(self._add_translations)
        self.langs = QWidget()
        self._langs_flow = FlowLayout(self.langs, spacing=10)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(self.title)
        titles.addWidget(self.facts)
        head.addLayout(titles, 1)
        head.addWidget(self.arabic_title)
        nav = QHBoxLayout()
        nav.addWidget(self.prev)
        nav.addWidget(self.next)
        nav.addSpacing(12)
        nav.addWidget(self.find, 1)
        nav.addWidget(self.add)

        self.body = QWidget()
        self.body.setObjectName("ResultsBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 8, 8, 28)
        self.body_layout.setSpacing(10)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        self.more = QPushButton()
        self.more.setObjectName("Quiet")
        self.more.clicked.connect(self._draw_more)

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        box.addLayout(head)
        box.addLayout(nav)
        box.addWidget(self.langs)
        # a language the reader reads with no translation downloaded yet (Q1d): offered in one click
        self.offer = QFrame()
        self.offer.setObjectName("Card")
        self._offer_box = QHBoxLayout(self.offer)
        self._offer_box.setContentsMargins(16, 8, 16, 8)
        self._offer_box.setSpacing(8)
        self.offer.setVisible(False)
        box.addWidget(self.offer)
        box.addWidget(self.scroll, 1)

    def set_connection(self, conn_of) -> None:
        self._conn_of = conn_of

    # ------------------------------------------------------------------ the languages shown
    def _chosen(self) -> list[str]:
        """The translations shown: the reader's own ticks, else one in each language the reader reads (Q1d)."""
        from isnady import config

        return core.shown(config.state_get("quran.editions"))

    def _fill_langs(self) -> None:
        while self._langs_flow.count():
            w = self._langs_flow.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        chosen = self._chosen()
        langs = core.wanted_languages()
        # in the order they are read: those shown first as shown, then the reader's languages, then the rest
        eds = sorted((e for e in core.editions() if e["key"] != core.ARABIC),
                     key=lambda e: (chosen.index(e["key"]) if e["key"] in chosen else len(chosen),
                                    langs.index(e["language"]) if e["language"] in langs else len(langs),
                                    e["language"], e["author"]))
        for e in eds:
            check = QCheckBox(f"{tr(e['language'])} — {e['author']}")
            check.setChecked(e["key"] in chosen)
            check.setToolTip(tr("Source: {source}", source=e["source"] or e["origin"]) + "\n"
                             + tr("Read from {origin}", origin=e["origin"]))
            check.toggled.connect(lambda on, k=e["key"]: self._toggle(k, on))
            self._langs_flow.addWidget(check)

    def _fill_offer(self) -> None:
        from isnady import config

        while self._offer_box.count():
            w = self._offer_box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        skipped = [x for x in str(config.state_get("quran.skip") or "").split(",") if x]
        missing = [lang for lang in core.missing_languages() if lang not in skipped]
        self.offer.setVisible(bool(missing) and core.available())
        if not missing:
            return
        names = ", ".join(tr(lang) for lang in missing)
        self._offer_box.addWidget(_label("📥 " + tr("No translation in {languages} is downloaded yet.", languages=names),
                                         "Lead"), 1)
        for lang in missing:
            key = core.DEFAULT_OF[lang]
            go = QPushButton(tr("Download {language}", language=tr(lang)))
            go.setObjectName("Primary")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.setToolTip(tr("The translation readers of {language} know best, from isnady-data; others with ➕ "
                             "Translations…", language=tr(lang)))
            go.clicked.connect(lambda _c=False, k=key, b=go: self._get_default(k, b))
            self._offer_box.addWidget(go)
        other = QPushButton(tr("Another translation…"))
        other.setObjectName("Quiet")
        other.setCursor(Qt.CursorShape.PointingHandCursor)
        other.clicked.connect(self._add_translations)
        self._offer_box.addWidget(other)
        close = QPushButton("✕")
        close.setObjectName("Quiet")
        close.setToolTip(tr("Do not offer it again"))
        close.clicked.connect(lambda: (config.state_set("quran.skip", ",".join(skipped + missing)),
                                       self.offer.setVisible(False)))
        self._offer_box.addWidget(close)

    def _get_default(self, key: str, button) -> None:
        from isnady import config

        saved = config.state_get("quran.editions")
        if saved is not None:                        # the reader's own ticks: the new one joins them
            config.state_set("quran.editions", ",".join(dict.fromkeys(core.shown(saved) + [key])))
        self._status = self.facts
        self.facts.setText(tr("Downloading …"))
        self._fetch([key], button)

    def _toggle(self, key: str, on: bool) -> None:
        from isnady import config

        chosen = [k for k in self._chosen() if k != key] + ([key] if on else [])
        config.state_set("quran.editions", ",".join(chosen) or ",")
        core._log().info("Qur'an translations shown: %s", ",".join(chosen) or "the Arabic alone")
        self.show_sura(self._sura, keep=True)

    # ------------------------------------------------------------------ downloading
    def _clear(self) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.more:
                w.setParent(None)
                w.deleteLater()

    def show_download(self) -> None:
        self._clear()
        self.title.setText(tr("The Qur'an"))
        self.arabic_title.setText("القرآن الكريم")
        self.facts.setText("")
        for w in (self.prev, self.next, self.find, self.add, self.langs, self.offer):
            w.setVisible(False)
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(24, 18, 24, 18)
        box.addWidget(_label(tr("The text of the Qur'an and its translations are downloaded once, on request, from "
                                "isnady-data: the Arabic (Tanzil's text) with a translation in each language you read "
                                "— {languages} — about 1 MB each; more translations can be added afterwards, of 98 "
                                "languages (those isnady-data does not keep are read from fawazahmed0/quran-api).",
                                languages=", ".join(tr(lang) for lang in core.wanted_languages())), "Lead"))
        go = QPushButton(tr("Download the Qur'an"))
        go.setObjectName("Primary")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status = _label("", "Caption")
        go.clicked.connect(lambda: self._fetch(core.default_editions(), go))
        row = QHBoxLayout()
        row.addWidget(go)
        row.addStretch(1)
        box.addLayout(row)
        box.addWidget(self._status)
        self.body_layout.addWidget(card)
        self.body_layout.addStretch(1)

    def _fetch(self, editions: list[str], button=None, info=None) -> None:
        if self._job is not None and self._job.isRunning():
            return
        if button is not None:
            button.setEnabled(False)
        self._job = _keep(_Fetch(editions, info))
        status = getattr(self, "_status", None)
        self._job.said.connect(lambda m: status and status.setText(m))
        self._job.ended.connect(self._fetched)
        self._job.start()

    def _fetched(self, error: str) -> None:
        if error:
            status = getattr(self, "_status", None)
            if status is not None:
                status.setText(tr("Not downloaded: {error}", error=error))
            if core.available():
                self._warn(tr("Not downloaded: {error}", error=error))
            return
        self.downloaded.emit()
        self.show_sura(self._sura)

    def _warn(self, text: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(self, tr("Translations of the Qur'an"),
                            text + "\n\n" + tr("The details are in the log: iy log --level warning"))

    def _add_translations(self) -> None:
        from isnady import config

        dialog = AddTranslations(self)
        if not dialog.exec():
            return
        if dialog.removed:
            for key in dialog.removed:
                core.remove(key)
            config.state_set("quran.editions", ",".join(k for k in self._chosen() if k not in dialog.removed) or ",")
        if dialog.chosen:
            config.state_set("quran.editions", ",".join(dict.fromkeys(self._chosen() + dialog.chosen)))
            self._status = self.facts
            self.facts.setText(tr("Downloading …"))
            self._fetch(dialog.chosen, info=dialog.info)
        elif dialog.removed:
            self.show_sura(self._sura, keep=True)

    # ------------------------------------------------------------------ a sura
    def show_sura(self, n: int, ayah: int | None = None, keep: bool = False) -> None:
        if not core.available():
            self.show_download()
            return
        if not 1 <= n <= 114:
            return
        for w in (self.prev, self.next, self.find, self.add, self.langs):
            w.setVisible(True)
        scroll = self.scroll.verticalScrollBar().value() if keep else 0
        self._sura, self._focus = n, ayah
        s = next(x for x in core.suras() if x["n"] == n)
        lang = i18n.language()
        name = {"tr": s["tr"], "ar": s["arabic"]}.get(lang) or f"{s['name']} — {s['english']}"
        self.title.setText(f"{n}. {name}")
        self.arabic_title.setText(s["arabic"])
        place = tr("Meccan") if s["place"] == "Mecca" else tr("Medinan")
        conn = self._conn_of()
        named = core.counts_by_sura(conn).get(n, 0) if conn is not None else 0
        self.facts.setText(tr("{verses} verses · {place}", verses=s["verses"], place=place)
                           + (" · " + tr("{n} hadith name its verses", n=named) if named else ""))
        self.prev.setEnabled(n > 1)
        self.next.setEnabled(n < 114)
        self._fill_langs()
        self._fill_offer()
        self._rows = core.verses(n, self._chosen())
        self._clear()
        self._shown = 0
        self._draw_more(until=ayah)
        if keep:
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(scroll))
        elif ayah:
            # once the cards above it are laid out (they settle their heights a moment after they are shown)
            for delay in (120, 400, 900):
                QTimer.singleShot(delay, self._scroll_to_focus)
        else:
            self.scroll.verticalScrollBar().setValue(0)

    def _draw_more(self, until: int | None = None) -> None:
        self.body_layout.removeWidget(self.more)
        self.more.setParent(None)
        stretch = self.body_layout.itemAt(self.body_layout.count() - 1)
        if stretch is not None and stretch.spacerItem() is not None:
            self.body_layout.takeAt(self.body_layout.count() - 1)
        end = max(self._shown + PAGE, until or 0)
        conn = self._conn_of()
        eds = {e["key"]: e for e in core.editions()}
        for row in self._rows[self._shown:end]:
            self.body_layout.addWidget(self._verse(row, eds, conn))
        self._shown = min(end, len(self._rows))
        left = len(self._rows) - self._shown
        if left > 0:
            self.more.setText(tr("Show {page} more verses ({left} left)", page=min(PAGE, left), left=left))
            self.more.setParent(self.body)
            self.body_layout.addWidget(self.more, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body_layout.addStretch(1)

    def _verse(self, row: dict, eds: dict, conn) -> QFrame:
        t = theme.current()
        card = QFrame()
        card.setObjectName("Card")
        card.setProperty("ayah", row["ayah"])
        box = QVBoxLayout(card)
        box.setContentsMargins(22, 12, 22, 12)
        box.setSpacing(6)
        arabic = row["texts"].get(core.ARABIC, "")
        font = theme.script_font("arabic")
        box.addWidget(TextBlock(f"<div dir='rtl' align='right' style='color:{theme.script_color('arabic')}'>"
                                f"{html.escape(arabic)} <span style='color:{t.gold}'>﴿{row['ayah']}﴾</span></div>",
                                font, rtl=True))
        for key in self._chosen():
            text = row["texts"].get(key)
            if not text:
                continue
            e = eds.get(key, {})
            rtl = e.get("direction") == "rtl"
            script = "arabic" if rtl else "latin"
            block = TextBlock(f"<div {'dir=rtl align=right' if rtl else ''} style='color:{theme.script_color(script)}'>"
                              f"{html.escape(text)}</div>", theme.script_font(script, factor=0.9), rtl=rtl)
            box.addWidget(block)
            box.addWidget(_label(f"{tr(e.get('language', ''))}, {e.get('author', '')}", "Caption"))
        foot = QHBoxLayout()
        ref = _label(f"{core.sura_name(self._sura, i18n.language())} {self._sura}:{row['ayah']}", "Caption", wrap=False)
        foot.addWidget(ref)
        hadith = core.hadith_of(conn, self._sura, row["ayah"]) if conn is not None else []
        if hadith:
            links = self._hadith_links(conn, hadith)
            foot.addSpacing(12)
            foot.addWidget(links, 1)
        else:
            foot.addStretch(1)
        box.addLayout(foot)
        return card

    def _hadith_links(self, conn, ids: list[int]) -> QWidget:
        """The hadith that name this verse — the Sunni books and the Shia books each on a line of its own (SH1) —
        their book and number, each a link to it in its book."""
        from isnady.core import titles

        marks = ",".join("?" * len(ids))
        rows = conn.execute(f"SELECT h.id, c.key, c.name, h.number, COALESCE(c.tradition, 'sunni') FROM hadiths h "
                            f"JOIN collections c ON c.id = h.collection_id WHERE h.id IN ({marks})", ids).fetchall()
        t = theme.current()
        holder = QWidget()
        lines = QVBoxLayout(holder)
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(2)
        for road, title in (("sunni", tr("Named in the Sunni books:")), ("shia", tr("Named in the Shia books:"))):
            mine = [r for r in rows if r[4] == road]
            if not mine:
                continue
            parts = [f"<a href='{hid}' style='color:{t.lapis if road == 'sunni' else t.gold};text-decoration:none'>"
                     f"{html.escape(titles.book(key, name))} {html.escape(str(number))}</a>"
                     for hid, key, name, number, _road in mine[:12]]
            more = f" … +{len(mine) - 12}" if len(mine) > 12 else ""
            label = _label("📜 " + title + " " + " · ".join(parts) + more, "Caption", rich=True)
            label.setToolTip(tr("Hadith whose translation marks this verse as the one it quotes or explains, e.g. "
                                "\"(33:33)\" — the translator's mark, not a reading of isnady's own. Click one to read "
                                "it in its book."))
            label.linkActivated.connect(lambda hid: self.open_hadith.emit(int(hid)))
            lines.addWidget(label)
        return holder

    def _scroll_to_focus(self) -> None:
        for i in range(self.body_layout.count()):
            w = self.body_layout.itemAt(i).widget()
            if w is not None and w.property("ayah") == self._focus:
                self.scroll.verticalScrollBar().setValue(max(0, w.y() - 20))
                w.setStyleSheet(f"QFrame#Card {{ border: 2px solid {theme.current().gold}; }}")
                break

    # ------------------------------------------------------------------ search
    def _search(self) -> None:
        text = self.find.text().strip()
        if not text:
            self.show_sura(self._sura)
            return
        found = core.search(text, self._chosen())
        self._clear()
        self.title.setText(tr("Search the Qur'an"))
        self.arabic_title.setText("")
        self.facts.setText(tr("{n} verses hold “{words}”", n=len(found), words=text) if len(found) < 200 else
                           tr("The first 200 verses that hold “{words}”", words=text))
        t = theme.current()
        lang = i18n.language()
        for r in found:
            card = QFrame()
            card.setObjectName("Card")
            box = QVBoxLayout(card)
            box.setContentsMargins(22, 10, 22, 10)
            go = QPushButton(f"{core.sura_name(r['sura'], lang)} {r['sura']}:{r['ayah']}")
            go.setObjectName("Link")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.clicked.connect(lambda _c=False, s=r["sura"], a=r["ayah"]: (self.find.clear(), self.show_sura(s, a)))
            rtl = r["edition"] == core.ARABIC
            box.addWidget(go, 0, Qt.AlignmentFlag.AlignLeft)
            script = "arabic" if rtl else "latin"
            box.addWidget(TextBlock(f"<div {'dir=rtl align=right' if rtl else ''} "
                                    f"style='color:{theme.script_color(script)}'>{html.escape(r['text'])}</div>",
                                    theme.script_font(script, factor=0.9 if not rtl else 1.0), rtl=rtl))
            self.body_layout.addWidget(card)
        if not found:
            self.body_layout.addWidget(_label(tr("No verse holds these words in the texts downloaded."), "Lead"))
        self.body_layout.addStretch(1)
        self.scroll.verticalScrollBar().setValue(0)
