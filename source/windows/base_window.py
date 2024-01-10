from __future__ import annotations

from modules.connection_manager import ConnectionManager
from modules.icons import Icons
from modules.settings import get_enable_high_dpi_scaling
from PyQt5.QtCore import QFile, QPoint, Qt, QTextStream
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication, QMainWindow

if get_enable_high_dpi_scaling():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)


class BaseWindow(QMainWindow):
    def __init__(self, parent=None, app: QApplication | None = None, version=None):
        super().__init__()
        self.parent = parent

        # Setup icons
        self.icons = Icons.get()

        if parent is None and app is not None:
            self.app = app
            self.version = version

            # Setup pool manager
            self.cm = ConnectionManager(version=version)
            self.cm.setup()
            self.manager = self.cm.manager

            # Setup font
            QFontDatabase.addApplicationFont(":resources/fonts/OpenSans-SemiBold.ttf")
            self.font_10 = QFont("Open Sans SemiBold", 10)
            self.font_10.setHintingPreference(QFont.PreferNoHinting)
            self.font_8 = QFont("Open Sans SemiBold", 8)
            self.font_8.setHintingPreference(QFont.PreferNoHinting)
            self.app.setFont(self.font_10)

            # Setup style
            file = QFile(":resources/styles/global.qss")
            file.open(QFile.ReadOnly | QFile.Text)
            self.style_sheet = QTextStream(file).readAll()
            self.app.setStyleSheet(self.style_sheet)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.pos = self.pos()
        self.pressing = False

        self.destroyed.connect(lambda: self._destroyed())

    def mousePressEvent(self, event):
        self.pos = event.globalPos()
        self.pressing = True
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.pressing:
            delta = QPoint(event.globalPos() - self.pos)
            self.moveWindow(delta, True)
            self.pos = event.globalPos()

    def moveWindow(self, delta, chain=False):
        self.move(self.x() + delta.x(), self.y() + delta.y())

        if chain and self.parent is not None:
            for window in self.parent.windows:
                if window is not self:
                    window.moveWindow(delta)

    def mouseReleaseEvent(self, QMouseEvent):
        self.pressing = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def showEvent(self, event):
        parent = self.parent

        if parent is not None:
            if self not in parent.windows:
                parent.windows.append(self)
                parent.show_signal.connect(self.show)
                parent.close_signal.connect(self.hide)

            if self.parent.isVisible():
                x = parent.x() + (parent.width() - self.width()) * 0.5
                y = parent.y() + (parent.height() - self.height()) * 0.5
            else:
                size = parent.app.screens()[0].size()
                x = (size.width() - self.width()) * 0.5
                y = (size.height() - self.height()) * 0.5

            self.move(int(x), int(y))
            event.accept()

    def _destroyed(self):
        if self.parent is not None:
            self.parent.windows.remove(self)
