from subprocess import Popen

from PyQt5.QtCore import QThread, pyqtSignal


class Observer(QThread):
    count_changed = pyqtSignal(int)
    append_proc = pyqtSignal(Popen)

    def __init__(self, parent):
        QThread.__init__(self)
        self.parent = parent
        self.processes = []
        self.append_proc.connect(self.handle_append_proc)

    def run(self):
        while self.parent:
            for proc in self.processes:
                if proc.poll() is not None:
                    proc.kill()
                    self.processes.remove(proc)
                    proc_count = len(self.processes)

                    if proc_count > 0:
                        self.count_changed.emit(proc_count)
                    else:
                        return

            QThread.sleep(1)

        return

    def handle_append_proc(self, proc):
        self.processes.append(proc)
        self.count_changed.emit(len(self.processes))
