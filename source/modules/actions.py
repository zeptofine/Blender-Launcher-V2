from __future__ import annotations

import logging
from collections import deque

from modules.action import Action
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot


class ActionQueue(deque[Action]):
    def __init__(self, worker_count=4, parent=None, maxlen=None, new_workers_on_crash=True):
        if maxlen:
            super().__init__(maxlen=maxlen)
        else:
            super().__init__()
        self.parent = parent
        self.workers: dict[ActionWorker, Action | None] = {}
        for i in range(worker_count):
            self.spawn_new_worker(readd_on_crash=new_workers_on_crash, name=str(i))

    def spawn_new_worker(self, start=False, readd_on_crash=False, name: str | None = None):
        w = ActionWorker(queue=self, parent=self.parent)

        def update_listener_dct(item, w=w):
            self.workers[w] = item
            logging.debug(f"{w}: {item}")

        w.item_changed.connect(update_listener_dct)
        if readd_on_crash:

            def remake_worker():
                self.workers.pop(w)
                self.spawn_new_worker(start, readd_on_crash, name)

            w.finished.connect(remake_worker)

        if name is not None:
            w.setObjectName(name)
        update_listener_dct(None)
        if start:
            w.start()

    def _remove_non_running(self):
        ws = list(self.workers)
        for worker in ws:
            if not worker.isRunning():
                self.workers.pop(worker)
                logging.debug("Popped", worker)

    def thread_with_action(self, action: Action):
        for listener, a in self.workers.items():
            if a == action:
                return listener
        return None

    def start(self):
        for worker in self.workers:
            worker.start()

    def fullstop(self):
        for worker in self.workers:
            if worker.isRunning():
                worker.fullstop()
                logging.debug(f"Stopped {worker} {self.workers[worker]}")

class ActionWorker(QThread):
    item_changed = pyqtSignal(object)  # Action | None

    def __init__(self, queue: ActionQueue, parent=None):
        super().__init__(parent)
        self.queue = queue
        self.item: Action | None = None

    def run(self):
        empty = False
        while True:
            try:
                self.item = self.queue.popleft()
            except IndexError:
                if empty:
                    QThread.msleep(500)
                else:
                    self.item_changed.emit(None)
                    empty = True
                continue

            empty = False
            self.item_changed.emit(self.item)
            self.item.run()

    @pyqtSlot()
    def fullstop(self):
        self.terminate()
        self.wait()

    def __repr__(self):
        return f"{self.__class__.__name__}[{self.objectName()}]"
