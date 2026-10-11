"""Genealogies (GEN1): the prophets' lineage, Quraysh (the Prophet's family ﷺ, the caliphs, the Imams), a
narrator's family read from the narrators' names, and a narrator's line of learning (teachers above, students
below) — drawn as trees one can zoom, move and click. Built on core.genealogy."""

from __future__ import annotations

import html

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from isnady.core import genealogy as core
from isnady.core import i18n
from isnady.core.i18n import N_, tr
from isnady.gui import theme

NODE_W, NODE_H, GAP_X, GAP_Y = 178, 50, 18, 42
# kind → (fill, border) in the light theme; the dark theme darkens the fills
KIND_STYLE = {"prophet": ("#F6E7BF", "#A47E24"), "caliph": ("#DCE7F5", "#1D4777"), "imam": ("#DDEFE3", "#2E7D5B"),
              "narrator": ("#FFFFFF", "#8A97A8"), "person": ("#F3F5F8", "#8A97A8")}
KIND_NAMES = {"prophet": N_("prophet"), "caliph": N_("caliph"), "imam": N_("Imam"), "narrator": N_("narrator"),
              "person": N_("person")}
VIEWS = (("prophets", N_("The prophets")), ("quraysh", N_("Quraysh and the Prophet's family")),
         ("family", N_("A narrator's family")), ("learning", N_("A narrator's line of learning")))


def _layout(tree: core.Tree, start: str, direction: int, x0: float = 0.0) -> dict[str, QPointF]:
    """A tidy tree: leaves side by side, a parent over the middle of its children; direction 1 grows down, -1 up."""
    pos: dict[str, QPointF] = {}
    cursor = [x0]

    def place(node_id: str, depth: int) -> float:
        node = tree.nodes[node_id]
        if not node.children:
            x = cursor[0]
            cursor[0] += NODE_W + GAP_X
        else:
            xs = [place(c, depth + 1) for c in node.children]
            x = (xs[0] + xs[-1]) / 2
        pos[node_id] = QPointF(x, direction * depth * (NODE_H + GAP_Y))
        return x
    place(start, 0)
    return pos


class _NodeItem(QGraphicsPathItem):
    def __init__(self, node: core.Node, view: "TreeView") -> None:
        super().__init__()
        self.node, self.view = node, view
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, NODE_W, NODE_H), 10, 10)
        self.setPath(path)
        t = theme.current()
        fill, border = KIND_STYLE.get(node.kind, KIND_STYLE["person"])
        fill_c = QColor(fill)
        if t.dark:
            fill_c = QColor(t.surface) if node.kind in ("narrator", "person") else fill_c.darker(330)
        self.setBrush(QBrush(fill_c))
        pen = QPen(QColor(border), 2.2 if node.kind != "narrator" else 1.2)
        if node.disputed:
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        latin = node.name()
        arabic = node.names.get("ar", "")
        ink = QColor(t.ink)
        top = QGraphicsSimpleTextItem(self)
        f = QFont(theme.reading_font(10.5, bold=True))
        top.setFont(f)
        top.setBrush(ink)
        top.setText(self._fit(latin, f, NODE_W - 14))
        top.setPos((NODE_W - top.boundingRect().width()) / 2, 5)
        if arabic and arabic != latin:
            low = QGraphicsSimpleTextItem(self)
            fa = theme.script_font("arabic", factor=0.62)
            low.setFont(fa)
            low.setBrush(QColor(theme.script_color("arabic")))
            low.setText(self._fit(arabic, fa, NODE_W - 14))
            low.setPos((NODE_W - low.boundingRect().width()) / 2, NODE_H - low.boundingRect().height() - 2)
        tip = [latin] + ([arabic] if arabic and arabic != latin else [])
        if node.count:
            tip.append(tr("{n:,} links in the imported chains", n=node.count))
        if node.gap:
            tip.append(tr("The generations between him and the one above are not known (dashed line)."))
        if node.disputed:
            tip.append(tr("Disputed: {note}", note=node.text("disputed")))
        if node.note:
            tip.append(node.text("note"))
        self.setToolTip("\n".join(tip))

    def paint(self, painter, option, widget=None) -> None:  # noqa: D102
        # Qt's own selection mark is a dashed frame — the sign of a disputed report here; the chosen box is drawn
        # with a thick border of the theme's colour instead
        from PySide6.QtWidgets import QStyle

        option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(QColor(theme.current().lapis), 3.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(-2, -2, NODE_W + 4, NODE_H + 4), 12, 12)

    @staticmethod
    def _fit(text: str, font: QFont, width: float) -> str:
        from PySide6.QtGui import QFontMetricsF

        return QFontMetricsF(font).elidedText(text, Qt.TextElideMode.ElideRight, width)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self.view.node_clicked.emit(self.node)
        super().mousePressEvent(e)


class TreeView(QGraphicsView):
    node_clicked = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.items_by_id: dict[str, _NodeItem] = {}

    def show_tree(self, tree: core.Tree, focus: str | None = None) -> None:
        scene = self.scene()
        scene.clear()
        self.items_by_id = {}
        t = theme.current()
        self.setBackgroundBrush(QColor(t.window))
        down = _layout(tree, tree.root, 1)
        pos = dict(down)
        if tree.up and tree.nodes[tree.up].children:
            up = _layout(tree, tree.up, -1)
            shift = pos[tree.root].x() - up[tree.up].x()
            for k, p in up.items():
                if k != tree.up:
                    pos[k] = QPointF(p.x() + shift, p.y())
        line = QPen(QColor(t.muted), 1.4)
        dashed = QPen(QColor(t.gold), 1.6, Qt.PenStyle.DashLine)
        # the lines first, under the boxes
        for node_id, p in pos.items():
            node = tree.nodes[node_id]
            parent = node.parent if node.parent != tree.up else tree.root
            if parent is None or parent not in pos:
                continue
            a, b = pos[parent], p
            upward = b.y() < a.y()
            ax, ay = a.x() + NODE_W / 2, a.y() + (0 if upward else NODE_H)
            bx, by = b.x() + NODE_W / 2, b.y() + (NODE_H if upward else 0)
            mid = (ay + by) / 2
            path = QPainterPath(QPointF(ax, ay))
            path.lineTo(ax, mid)
            path.lineTo(bx, mid)
            path.lineTo(bx, by)
            edge = scene.addPath(path, dashed if node.gap else line)
            edge.setZValue(-1)
        for node_id, p in pos.items():
            item = _NodeItem(tree.nodes[node_id], self)
            item.setPos(p)
            scene.addItem(item)
            self.items_by_id[node_id] = item
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self.resetTransform()
        QTimer.singleShot(0, lambda: self.centre(focus or tree.root))

    def centre(self, node_id: str) -> None:
        item = self.items_by_id.get(node_id)
        if item:
            self.scene().clearSelection()
            item.setSelected(True)
            self.centerOn(item)

    def wheelEvent(self, e) -> None:  # noqa: N802
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def zoom(self, factor: float) -> None:
        self.scale(factor, factor)

    def fit(self) -> None:
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


class GenealogyPage(QWidget):
    open_narrator = Signal(int)

    def __init__(self, connection, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._connection = connection
        self.tree: core.Tree | None = None
        self.view_key = "prophets"
        self.person_id: int | None = None

        top = QHBoxLayout()
        heading = _label(tr("Genealogies"), "PageTitle", wrap=False)
        heading.setFont(theme.reading_font(22, bold=True))
        top.addWidget(heading)
        top.addSpacing(16)
        self.group = QButtonGroup(self)
        for key, label in VIEWS:
            b = QPushButton(tr(label))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self.show_view(k))
            self.group.addButton(b)
            b.setProperty("key", key)
            top.addWidget(b)
        top.addStretch(1)

        find_row = QHBoxLayout()
        self.find = QLineEdit()
        self.find.setClearButtonEnabled(True)
        self.find.returnPressed.connect(self._find)
        self.find.textChanged.connect(lambda _t: self._find_live())
        find_row.addWidget(self.find, 1)
        for text, tip, slot in (("−", tr("Smaller"), lambda: self.view.zoom(1 / 1.25)),
                                ("+", tr("Larger"), lambda: self.view.zoom(1.25)),
                                (tr("Whole tree"), tr("Fit the whole tree in the window"), lambda: self.view.fit())):
            b = QPushButton(text)
            b.setObjectName("Quiet")
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            find_row.addWidget(b)
        self.results = QListWidget()
        self.results.setMaximumHeight(170)
        self.results.hide()
        self.results.itemClicked.connect(self._picked)

        self.view = TreeView()
        self.view.node_clicked.connect(self._clicked)
        board = QFrame()
        board.setObjectName("Card")
        bbox = QVBoxLayout(board)
        bbox.setContentsMargins(4, 4, 4, 4)
        bbox.addWidget(self.view)

        self.side = QFrame()
        self.side.setObjectName("Card")
        self.side.setFixedWidth(310)
        self.side_box = QVBoxLayout(self.side)
        self.side_box.setContentsMargins(18, 16, 18, 16)
        self.side_box.setSpacing(8)

        self.caption = _label("", "Caption", rich=True)
        middle = QHBoxLayout()
        middle.setSpacing(14)
        middle.addWidget(board, 1)
        middle.addWidget(self.side)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(10)
        root.addLayout(top)
        root.addLayout(find_row)
        root.addWidget(self.results)
        root.addLayout(middle, 1)
        root.addWidget(self.caption)
        self._started = False

    @property
    def conn(self):
        return self._connection() if callable(self._connection) else self._connection

    # ------------------------------------------------------------------ views
    def ensure(self) -> None:
        if not self._started:
            self._started = True
            self.show_view(self.view_key)

    def show_view(self, key: str, person_id: int | None = None) -> None:
        self._started = True
        self.view_key = key
        for b in self.group.buttons():
            b.setChecked(b.property("key") == key)
        if person_id is not None:
            self.person_id = person_id
        self.results.hide()
        t = theme.current()
        legend = (f"<span style='color:{KIND_STYLE['prophet'][1]}'>■</span> {tr('prophet')} &nbsp; "
                  f"<span style='color:{KIND_STYLE['caliph'][1]}'>■</span> {tr('caliph')} &nbsp; "
                  f"<span style='color:{KIND_STYLE['imam'][1]}'>■</span> {tr('Imam')} &nbsp; "
                  f"<span style='color:{t.gold}'>╌</span> {tr('generations between not known')} &nbsp; "
                  f"▭ {tr('dashed box: the reports differ')}")
        if key in core.WRITTEN:
            self.find.setPlaceholderText(tr("Find in this tree: Ibrahim, Musa, Hashim, Ali …"))
            self.tree = core.written(key)
            self.view.show_tree(self.tree)
            if key == "prophets":
                about = tr("Sources: the Qur'an where it names a relation; al-Bukhari, Sahih (Manaqib al-Ansar: the "
                           "Prophet's lineage up to 'Adnan); Ibn Hisham, al-Sira; Ibn Sa'd, al-Tabaqat; al-Tabari, "
                           "Tarikh; Ibn Kathir, al-Bidaya wa-l-Nihaya. The names between Adam and Ibrahim and between "
                           "Isma'il and 'Adnan are the historians'; they took them partly from the People of the Book, "
                           "and neither the Qur'an nor an authentic hadith gives them. Click a name for what the "
                           "sources say.")
            else:
                about = tr("Sources: Ibn Hisham, al-Sira; Ibn Sa'd, al-Tabaqat; Mus'ab al-Zubayri, Nasab Quraysh; "
                           "Ibn Hazm, Jamharat Ansab al-'Arab. The line of the Prophet's family ﷺ down to the Imams "
                           "is recorded by the Sunni genealogists too; that they are Imams is the Shia's belief and "
                           "is shown as theirs. Click a name for what the sources say.")
            self.caption.setText(legend + "<br>" + about)
            self._show_node(self.tree.nodes[self.tree.root])
            return
        self.find.setPlaceholderText(tr("A narrator: name, kunya or nisba — Arabic or Latin letters"))
        conn = self.conn
        if conn is None:
            return
        if self.person_id is None:
            self.person_id = conn.execute(
                "SELECT person_id FROM isnad_links WHERE person_id IS NOT NULL GROUP BY person_id "
                "ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0] if conn.execute(
                "SELECT 1 FROM isnad_links WHERE person_id IS NOT NULL LIMIT 1").fetchone() else None
        if self.person_id is None:
            self._side([_label(tr("No narrator is identified in the imported chains yet."), "Lead")])
            return
        if key == "family":
            tree = core.family(conn, self.person_id)
            if tree is None:
                self.view.scene().clear()
                self.tree = None
                name = core._person_node(conn, self.person_id, None).name()
                self._side([_label(tr("No kin of {name} among the narrators: no narrator's name makes him a father or a "
                                      "son. Try another narrator, or his line of learning.", name=name), "Lead")])
                self.caption.setText(self._family_note())
                return
            self.tree = tree
            self.view.show_tree(tree, f"p{self.person_id}")
            self.caption.setText(legend.split(" &nbsp; <span style='color:" + t.gold)[0] + "<br>" + self._family_note())
        else:
            self.tree = core.learning(conn, self.person_id)
            self.view.show_tree(self.tree)
            self.caption.setText(tr("His teachers above him and their teachers, his students below him and theirs — the "
                                    "four most frequent at each step, counted from the imported chains (the number "
                                    "in each box when you point at it). A line of learning, not of blood."))
        self._show_node(self.tree.nodes[f"p{self.person_id}"])

    def _family_note(self) -> str:
        conn = self.conn
        return tr("A family read from the narrators' own names: \"X b. Y b. Z\" is taken as the son of \"Y b. Z\" when "
                  "exactly one narrator of the same tradition and of an earlier or the same generation has that name — "
                  "{n:,} such links in the imported rijal works. A reading of the names, to be checked against the "
                  "biographies.", n=core.family_count(conn) if conn is not None else 0)

    def _clicked(self, node: core.Node) -> None:
        self.view.scene().clearSelection()
        item = self.view.items_by_id.get(node.id)
        if item:
            item.setSelected(True)
        self._show_node(node)

    # ------------------------------------------------------------------ the side panel
    def _side(self, widgets: list) -> None:
        while self.side_box.count():
            item = self.side_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for w in widgets:
            self.side_box.addWidget(w)
        self.side_box.addStretch(1)

    def _show_node(self, node: core.Node) -> None:
        t = theme.current()
        widgets = []
        name = _label(html.escape(node.name()), "CardTitle", rich=True)
        name.setFont(theme.reading_font(17, bold=True))
        widgets.append(name)
        arabic = node.names.get("ar")
        if arabic and arabic != node.name():
            ar = QLabel(arabic)
            ar.setFont(theme.script_font("arabic", bold=True, factor=1.0))
            ar.setStyleSheet(f"color: {theme.script_color('arabic')};")
            ar.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            widgets.append(ar)
        others = [f"{lang}: <i>{html.escape(node.names[code])}</i>" for code, lang in
                  (("en", "English"), ("tr", "Türkçe")) if node.names.get(code) and node.names[code] != node.name()]
        if others and node.kind != "narrator":
            widgets.append(_label(" &nbsp;·&nbsp; ".join(others), "Caption", rich=True))
        colour = KIND_STYLE.get(node.kind, KIND_STYLE["person"])[1]
        widgets.append(_label(f"<span style='color:{colour}'>■</span> {html.escape(tr(KIND_NAMES.get(node.kind, 'person')))}",
                              "Caption", rich=True))
        if self.tree is not None and self.view_key in core.WRITTEN:
            line = core.path_to(self.tree, node.id)
            if len(line) > 1:
                parent = line[-2]
                widgets.append(_label(tr("Son of {parent}", parent=html.escape(parent.name()))
                                      + (" — " + tr("generations between not known") if node.gap else ""), "Lead", rich=True))
            kids = [self.tree.nodes[c].name() for c in node.children]
            if kids:
                widgets.append(_label(tr("Children shown: {names}", names=html.escape(", ".join(kids))), "Lead", rich=True))
            if len(line) > 1:
                widgets.append(_label(tr("{n} generations from {root}", n=len(line) - 1,
                                         root=html.escape(line[0].name())), "Caption", rich=True))
        if node.note:
            widgets.append(_label(html.escape(node.text("note")), "Lead", rich=True))
        if node.disputed:
            box = _label("⚠ " + html.escape(node.text("disputed")), "Lead", rich=True)
            box.setStyleSheet(f"background: {t.gilt}; color: {t.ink}; border-radius: 8px; padding: 6px 8px;")
            widgets.append(box)
        if node.count:
            widgets.append(_label(tr("{n:,} links in the imported chains", n=node.count), "Caption"))
        if node.person_id is not None:
            row = QVBoxLayout()
            row.setSpacing(2)
            holder = QWidget()
            holder.setLayout(row)
            for text, slot in ((tr("Open in Narrators"), lambda: self.open_narrator.emit(node.person_id)),
                               (tr("His family"), lambda: self.show_view("family", node.person_id)),
                               (tr("His line of learning"), lambda: self.show_view("learning", node.person_id))):
                b = QPushButton(text)
                b.setObjectName("Link")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(slot)
                row.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
            widgets.append(holder)
            try:
                from isnady.core import bookmarks
                from isnady.gui.bookmarks_page import BookmarkButton

                ref = bookmarks.narrator_ref(self.conn, node.person_id)
                if ref:
                    star_row = QHBoxLayout()
                    star_holder = QWidget()
                    star_holder.setLayout(star_row)
                    star_row.addWidget(BookmarkButton("narrator", *ref))
                    star_row.addWidget(_label(tr("Bookmark this narrator"), "Caption"))
                    star_row.addStretch(1)
                    widgets.append(star_holder)
            except Exception:          # bookmarks are a convenience: never stop the tree
                pass
        self._side(widgets)

    # ------------------------------------------------------------------ finding
    def _find_live(self) -> None:
        if self.view_key in core.WRITTEN and self.tree is not None and len(self.find.text().strip()) >= 2:
            hits = core.find(self.tree, self.find.text())
            if hits:
                self.view.centre(hits[0].id)

    def _find(self) -> None:
        text = self.find.text().strip()
        if not text:
            return
        if self.view_key in core.WRITTEN and self.tree is not None:
            hits = core.find(self.tree, text)
            if hits:
                self.view.centre(hits[0].id)
                self._show_node(hits[0])
            return
        conn = self.conn
        if conn is None:
            return
        from isnady.core import narrators

        rows, _total = narrators.find(conn, text)
        self.results.clear()
        for r in rows[:30]:
            view = r.get("view") or {}
            label = (view.get("reading") or view.get("full_reading") or "") + "   " + (view.get("arabic") or r["name"])
            item = QListWidgetItem(label.strip())
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.results.addItem(item)
        self.results.setVisible(bool(rows))

    def _picked(self, item: QListWidgetItem) -> None:
        self.results.hide()
        self.show_view(self.view_key, item.data(Qt.ItemDataRole.UserRole))

    def show_person(self, person_id: int, which: str = "family") -> None:
        self.show_view(which, person_id)

    def retheme(self) -> None:
        if self._started:
            self.show_view(self.view_key)


_WORDS = (N_("Family"), N_("Line of learning"), N_("teachers (above):"), N_("students (below):"),
          N_("generations between not known"), N_("disputed"))
_ = i18n
