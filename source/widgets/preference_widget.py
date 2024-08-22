

from modules.config_info import ConfigInfo
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)
from widgets.base_build_widget import BaseBuildWidget
from widgets.elided_text_label import ElidedTextLabel


class PreferenceWidget(BaseBuildWidget):
    delete_requested = pyqtSignal(str)

    def __init__(self, info: ConfigInfo, parent=None):
        super().__init__(parent)
        self.info = info

        self.layout: QHBoxLayout = QHBoxLayout()
        self.layout.setContentsMargins(2, 2, 0, 2)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(self.layout)

        self.draw()

    def draw(self):
        self.delete_button = QPushButton("Delete", self)
        self.delete_button.setFixedWidth(85)
        self.delete_button.setProperty("CancelButton", True)
        self.target_ver_label = QLabel(str(self.info.target_version), self)
        self.target_ver_label.setFixedWidth(100)
        self.target_ver_label.setIndent(20)
        self.name_label = ElidedTextLabel(self.info.name, self)


        self.layout.addWidget(self.delete_button)
        self.layout.addWidget(self.target_ver_label)
        self.layout.addWidget(self.name_label, stretch=1)


    def _request_delete(self):
        self.delete_requested.emit(self.info.name)
