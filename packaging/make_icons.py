"""The isnady application icon, drawn with Qt and the bundled Amiri font: the word إسناد in gold on the
lapis of the sidebar, in every size the three systems ask for. Writes:
  src/isnady/assets/icons/isnady.png (512, the window icon), packaging/isnady.ico (Windows),
  packaging/isnady.icns (macOS), packaging/isnady.png (256, Linux AppImage).
Run: python packaging/make_icons.py   (needs PySide6 and Pillow)"""

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter, QPainterPath

ROOT = Path(__file__).resolve().parent.parent
LAPIS, LAPIS_DEEP, GOLD = QColor("#1E3A5F"), QColor("#142A47"), QColor("#C9A227")


def draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    m = size * 0.06
    rect = QRectF(m, m, size - 2 * m, size - 2 * m)
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.2, size * 0.2)
    p.fillPath(path, LAPIS)
    # a thin gold rule above and below, like a page's frame
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(GOLD)
    for y in (0.27, 0.73):
        p.drawRoundedRect(QRectF(size * 0.24, size * y, size * 0.52, size * 0.018), size * 0.009, size * 0.009)
    families = QFontDatabase.applicationFontFamilies(_FONT_ID)
    font = QFont(families[0] if families else "Amiri")
    font.setBold(True)
    font.setPixelSize(int(size * (0.30 if size >= 48 else 0.38)))
    p.setFont(font)
    p.setPen(GOLD)
    p.drawText(rect.adjusted(0, -size * 0.03, 0, -size * 0.03), Qt.AlignmentFlag.AlignCenter, "إسناد")
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv[:1])
    _FONT_ID = QFontDatabase.addApplicationFont(str(ROOT / "src/isnady/assets/fonts/Amiri-Bold.ttf"))
    out = ROOT / "packaging"
    tmp = out / "icon-build"
    tmp.mkdir(exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256, 512, 1024]
    for s in sizes:
        draw(s).save(str(tmp / f"isnady-{s}.png"))
    draw(512).save(str(ROOT / "src/isnady/assets/icons/isnady.png"))
    draw(256).save(str(out / "isnady.png"))
    from PIL import Image

    images = [Image.open(tmp / f"isnady-{s}.png") for s in sizes]
    images[-1].save(out / "isnady.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    Image.open(tmp / "isnady-1024.png").save(out / "isnady.icns")
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    print("icons written")
