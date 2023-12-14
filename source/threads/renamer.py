from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal


class Renamer(QThread):
    completed = pyqtSignal([Path], [])

    def __init__(self, src_path, dst_name, parent=None):
        QThread.__init__(self)
        self.src_path = src_path
        self.dst_name = (dst_name.lower()).replace(" ", "-")
        self.parent = parent

    def run(self):

        if self.parent is not None:
            while self.parent.renamer_count > 0:
                QThread.msleep(250)

            self.parent.renamer_count += 1

        try:
            dst = Path(self.src_path).parent / self.dst_name
            self.src_path.rename(dst)
            self.completed.emit(dst)
        except OSError:
            self.completed.emit()

        if self.parent is not None:
            self.parent.remover_count -= 1

