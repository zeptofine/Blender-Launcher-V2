from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtNetwork import QLocalServer
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QHBoxLayout,
    QLabel,
    QLayoutItem,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from windows.base_window import BaseWindow


class WindowHeader(QWidget):
    minimize_signal = pyqtSignal()
    close_signal = pyqtSignal()

    def __init__(
        self,
        parent: BaseWindow,
        label: str = "",
        widgets: Iterable[QWidget] = (),
        use_minimize: bool = True,
    ):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.layout_ = layout
        self.setLayout(layout)

        margins = 0
        for widget in widgets:
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignLeft)
            margins -= 1

        self.label = QLabel(label, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label, 1)

        self.minimize_button = None
        if use_minimize:
            self.minimize_button = QPushButton(parent.icons.minimize, "")
            self.minimize_button.setIconSize(QSize(20, 20))
            self.minimize_button.setFixedSize(36, 32)
            self.minimize_button.setProperty("HeaderButton", True)
            layout.addWidget(self.minimize_button, 0, Qt.AlignmentFlag.AlignRight)
            margins += 1

        self.close_button = QPushButton(parent.icons.close, "")
        self.close_button.setIconSize(QSize(20, 20))
        self.close_button.setFixedSize(36, 32)
        self.close_button.setProperty("HeaderButton", True)
        self.close_button.setProperty("CloseButton", True)
        self.close_button.clicked.connect(self.close_signal.emit)
        margins += 1
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignRight)

        # make sure the label is centered despite the buttons surrounding the label
        layout.setContentsMargins(max(int(margins * 36), 0), 0, 0, 0)
