from shutil import rmtree

from PyQt5.QtCore import QThread, pyqtSignal


class Remover(QThread):
    completed_removal = pyqtSignal(int)

    def __init__(self, path, parent=None):
        QThread.__init__(self)
        self.path = path
        self.parent = parent

    def run(self):

        if self.parent is not None:
            while self.parent.remover_count > 0:
                QThread.msleep(250)

            self.parent.remover_count += 1

        try:
            rmtree(self.path.as_posix())
            self.completed_removal.emit(0)
        except OSError:
            self.completed_removal.emit(1)

        if self.parent is not None:
            self.parent.remover_count -= 1

