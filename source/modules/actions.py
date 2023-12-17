from __future__ import annotations

from queue import Queue
from typing import TYPE_CHECKING

from modules.action import Action
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot


class ActionQueue(Queue[Action]):
    def __init__(self, worker_count=4, parent=None, maxsize=0):
        super().__init__(maxsize=maxsize)
        self._lst = []
        self.workers: dict[ActionWorker, Action | None] = dict.fromkeys(
            [ActionWorker(queue=self, parent=parent) for _ in range(worker_count)]
        )

        for listener in self.workers:
            def update_listener_dct(item, listener=listener):
                self.workers[listener] = item
            listener.item_changed.connect(update_listener_dct)


    def start(self):
        for worker in self.workers:
            worker.start()

    def fullstop(self):
        for worker in self.workers:
            worker.fullstop()


class ActionWorker(QThread):
    item_changed = pyqtSignal(Action)

    def __init__(self, queue: ActionQueue, parent=None):
        super().__init__(parent)
        self.queue = queue
        self.item: Action | None = None

    def run(self):
        while True:
            self.item = self.queue.get()
            self.item_changed.emit(self.item)
            self.item.run()


    @pyqtSlot()
    def fullstop(self):
        self.terminate()
        self.wait()
