from enum import Enum

from modules.config_info import ConfigInfo, config_path_name
from modules.settings import get_library_folder
from modules.tasks import TaskQueue
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)
from semver import Version
from widgets.base_build_widget import BaseBuildWidget
from windows.dialog_window import DialogWindow


class PreferenceWidget(BaseBuildWidget):
    def __init__(self, info: ConfigInfo, parent=None):
        super().__init__(parent)
        self.info = info
