from datetime import datetime

from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy


class DateTimeWidget(QPushButton):
    left_arrow = "◂"
    right_arrow = "▸"
    str_format = "%d %b %Y, %H:%M"

    def __init__(self, dt: datetime, build_hash: str):
        super().__init__()
        self.build_hash = build_hash

        self.setProperty("TextOnly", True)

        self.layout: QHBoxLayout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.datetimeStr = dt.strftime(self.str_format)
        self.datetimeLabel = QLabel(self.datetimeStr)
        self.datetimeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_metrics = self.datetimeLabel.fontMetrics()

        self.setMinimumWidth(self.font_metrics.width(f"{self.left_arrow}{self.datetimeStr}{self.right_arrow}"))

        if self.build_hash is not None:
            self.LeftArrowLabel = QLabel(self.left_arrow)
            self.LeftArrowLabel.setVisible(False)
            self.RightArrowLabel = QLabel(self.right_arrow)
            self.RightArrowLabel.setVisible(False)

            self.BuildHashLabel = QLabel(self.build_hash)
            self.BuildHashLabel.hide()

            self.layout.addWidget(self.LeftArrowLabel)
            self.layout.addStretch()
            self.layout.addWidget(self.datetimeLabel)
            self.layout.addWidget(self.BuildHashLabel)
            self.layout.addStretch()
            self.layout.addWidget(self.RightArrowLabel)

            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Press to show build hash number")
            self.clicked.connect(self.toggle_visibility)
        else:
            self.layout.addWidget(self.datetimeLabel)

    def toggle_visibility(self):
        self.datetimeLabel.setVisible(not self.datetimeLabel.isVisible())
        self.BuildHashLabel.setVisible(not self.BuildHashLabel.isVisible())

        if self.BuildHashLabel.isVisible():
            self.setToolTip("Press to show date and time")
        else:
            self.setToolTip("Press to show build hash number")

    def enterEvent(self, event: QtCore.QEvent) -> None:
        if self.build_hash is not None:
            self.LeftArrowLabel.setVisible(True)
            self.RightArrowLabel.setVisible(True)

        return super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        if self.build_hash is not None:
            self.LeftArrowLabel.setVisible(False)
            self.RightArrowLabel.setVisible(False)

        return super().leaveEvent(event)
