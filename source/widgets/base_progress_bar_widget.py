from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QProgressBar


class BaseProgressBarWidget(QProgressBar):
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.title = ""

        self.setAlignment(Qt.AlignCenter)
        self.setMinimum(0)
        self.set_progress(0, 0)

    def set_title(self, title: str):
        self.title = title
        self.setFormat(f"{self.title}: {self.last_progress[0]:.1f} of {self.last_progress[1]:.1f} MB")

    @pyqtSlot(int, int)
    def set_progress(self, obtained: int, total: int, title: str | None = None):
        if title is not None and title != self.title:
            self.title = title

        # Convert bytes to megabytes
        obtained = obtained / 1048576
        total = total / 1048576

        # Update appearance
        self.setMaximum(total)
        self.setValue(obtained)

        # Repaint and call signal
        self.setFormat(f"{self.title}: {obtained:.1f} of {total:.1f} MB")
        self.progress_updated.emit(obtained, total)
        self.last_progress = (obtained, total)
