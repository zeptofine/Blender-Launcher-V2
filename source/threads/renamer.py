from dataclasses import dataclass
from pathlib import Path

from modules.task import Task
from PyQt5.QtCore import pyqtSignal


@dataclass(frozen=True)
class RenameTask(Task):
    src: Path
    dst_name: str

    finished = pyqtSignal(Path)
    failure = pyqtSignal()

    def run(self):
        try:
            dst = self.src.parent / self.dst_name.lower().replace(" ", "-")
            self.src.rename(dst)
            self.finished.emit(dst)
        except OSError:
            self.failure.emit()
            raise

    def __str__(self):
        return f"Rename {self.src} to {self.dst_name}"
