from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree

from modules.action import Action
from PyQt5.QtCore import pyqtSignal


@dataclass
class RemoveAction(Action):
    path: Path
    finished = pyqtSignal(bool)

    def run(self):
        try:
            rmtree(self.path.as_posix())
            self.finished.emit(0)
        except OSError:
            self.finished.emit(1)

