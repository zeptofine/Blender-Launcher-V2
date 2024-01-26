from abc import abstractmethod

from modules.enums import MessageType
from PyQt5.QtCore import QObject, pyqtSignal


class Task(QObject):
    message = pyqtSignal(str, MessageType)

    def __post_init__(self):
        super().__init__()

    @abstractmethod
    def run(self):
        raise NotImplementedError
