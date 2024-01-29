from enum import Enum


class MessageType(Enum):
    NEWBUILDS = 1
    DOWNLOADFINISHED = 2
    ERROR = 3
