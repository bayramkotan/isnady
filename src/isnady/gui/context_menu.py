"""Right-click menus (CTX1): the same actions as the buttons of a page, where the reader's hand already is.

A menu is a list of entries:
    (text, callable)          an action; callable None → shown greyed
    (text, [entries])         a submenu
    None                      a separator
Every menu is built when it is asked for, so it shows the state of that moment (a bookmark added, a marker removed).
"""

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMenu, QWidget


def build(parent: QWidget, entries: list) -> QMenu:
    menu = QMenu(parent)
    _fill(menu, entries)
    return menu


def _fill(menu: QMenu, entries: list) -> None:
    last_separator = True
    for entry in entries:
        if entry is None:
            if not last_separator:
                menu.addSeparator()
                last_separator = True
            continue
        text, what = entry
        if isinstance(what, list):
            if not what:
                continue
            sub = menu.addMenu(text)
            _fill(sub, what)
        else:
            action = menu.addAction(text)
            if what is None:
                action.setEnabled(False)
            else:
                action.triggered.connect(lambda _c=False, f=what: f())
        last_separator = False


def popup(parent: QWidget, global_pos, entries: list) -> None:
    """Show the menu at the pointer; nothing when there is nothing to offer."""
    if any(e is not None for e in entries):
        build(parent, entries).exec(global_pos)


def copy(text: str) -> None:
    QGuiApplication.clipboard().setText(text or "")


def bookmark_entry(kind: str, ref: str | None, title: str, subtitle: str = ""):
    """☆ Add to bookmarks / ★ Remove from bookmarks, as the page's star does."""
    from isnady.core.i18n import tr
    from isnady.gui import bookmarks_page

    if not ref:
        return None
    marked = bookmarks_page.store().find(kind, str(ref)) is not None
    return ((("★  " + tr("Remove from bookmarks")) if marked else ("☆  " + tr("Add to bookmarks"))),
            lambda: bookmarks_page.toggle(kind, str(ref), title, subtitle))
