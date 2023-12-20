from dataclasses import dataclass

from PyQt5.QtGui import QColor, QIcon, QPixmap

base_path = ":resources/icons/"

WHITE = QColor(255, 255, 255, 255)



@dataclass
class Icons:
    settings: QIcon
    wiki: QIcon
    minimize: QIcon
    close: QIcon
    folder: QIcon
    favorite: QIcon
    fake: QIcon
    delete: QIcon
    filled_circle: QIcon
    quick_launch: QIcon
    download: QIcon
    file: QIcon
    taskbar: QIcon

    @classmethod
    def get(cls, color=WHITE):
        return cls(
        load_icon(color, "settings"),
        load_icon(color, "wiki"),
        load_icon(color, "minimize"),
        load_icon(color, "close"),
        load_icon(color, "folder"),
        load_icon(color, "favorite"),
        load_icon(color, "fake"),
        load_icon(color, "delete"),
        load_icon(color, "filled_circle"),
        load_icon(color, "quick_launch"),
        load_icon(color, "download"),
        load_icon(color, "file"),
        QIcon(base_path + "bl/bl.ico"),
    )

def load_icon(color, name):
    pixmap = QPixmap(base_path + name + "")
    image = pixmap.toImage()

    for y in range(image.height()):
        for x in range(image.height()):
            color.setAlpha(image.pixelColor(x, y).alpha())
            image.setPixelColor(x, y, color)

    pixmap = QPixmap.fromImage(image)
    return QIcon(pixmap)
