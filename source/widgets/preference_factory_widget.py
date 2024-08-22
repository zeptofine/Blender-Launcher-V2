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


class PreferenceFactoryState(Enum):
    READY = 0
    CREATING = 1


class PreferenceFactoryWidget(BaseBuildWidget):
    config_created = pyqtSignal(ConfigInfo)

    def __init__(self, parent, list_widget, task_queue: TaskQueue):
        super().__init__(parent=parent)
        self.setAcceptDrops(False)

        self.list_widget = list_widget
        self.task_queue = task_queue
        self.existing_configs: list[str] = []  # Used to check if the name is already taken

        # box should highlight when dragged over
        self.layout: QGridLayout = QGridLayout()
        self.layout.setContentsMargins(2, 2, 0, 2)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(self.layout)
        self.draw()
        self.update_state(PreferenceFactoryState.READY)

    def draw(self):
        self.creation_button = QPushButton("Create...", self)
        self.creation_button.setFixedWidth(85)
        self.creation_button.setProperty("CreateButton", True)
        self.creation_button.pressed.connect(self.start_creation)

        self.name_text_label = QLabel("Config name", self)
        self.name_text_label.setContentsMargins(2, 0, 0, 0)
        self.name_text_edit = QLineEdit(self)
        self.name_text_edit.textChanged.connect(self.text_changed)

        self.target_version_label = QLabel("target")
        self.target_version_label.setContentsMargins(2, 0, 0, 0)
        self.target_version_dial = QDoubleSpinBox(self)
        self.target_version_dial.setFixedWidth(85)
        self.target_version_dial.setMinimum(1.0)
        self.target_version_dial.setDecimals(2)
        self.target_version_dial.setSingleStep(0.1)

        self.confirm_button = QPushButton("Confirm", self)
        self.confirm_button.setFixedWidth(85)
        self.confirm_button.setProperty("LaunchButton", True)
        self.confirm_button.pressed.connect(self.confirm)
        self.confirm_button.setEnabled(False)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setFixedWidth(85)
        self.cancel_button.setProperty("CancelButton", True)
        self.cancel_button.pressed.connect(self.cancel)

        self.layout.addWidget(self.creation_button, 0, 0, 1, 1)
        self.layout.addWidget(self.name_text_label, 0, 1, 1, 1)
        self.layout.addWidget(self.name_text_edit, 1, 1, 1, 1)
        self.layout.addWidget(self.target_version_label, 0, 2, 1, 1)
        self.layout.addWidget(self.target_version_dial, 1, 2, 1, 1)
        self.layout.addWidget(self.confirm_button, 0, 3, 2, 1)
        self.layout.addWidget(self.cancel_button, 0, 4, 2, 1)

        self.creation_button.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_state(self, state: PreferenceFactoryState):
        self.state = state
        if state == PreferenceFactoryState.READY:
            self.creation_button.show()
            self.name_text_label.hide()
            self.name_text_edit.hide()
            self.name_text_edit.clear()
            self.target_version_label.hide()
            self.target_version_dial.hide()
            self.target_version_dial.setValue(4.02)
            self.confirm_button.hide()
            self.cancel_button.hide()
        elif state == PreferenceFactoryState.CREATING:
            self.creation_button.hide()
            self.name_text_label.show()
            self.name_text_edit.show()
            self.target_version_label.show()
            self.target_version_dial.show()
            self.confirm_button.show()
            self.cancel_button.show()

    def update_existing_configs(self, existing: list[str]):
        self.existing_configs = existing

    def start_creation(self):
        self.update_state(PreferenceFactoryState.CREATING)

    def text_changed(self):
        if s := self.name_text_edit.text().strip():
            if s in self.existing_configs:
                self.name_text_label.setText("Name is already taken!")
            else:
                self.name_text_label.setText("Config name")
            self.confirm_button.setEnabled(True)
        else:
            self.confirm_button.setEnabled(False)

    def cancel(self):
        self.update_state(PreferenceFactoryState.READY)

    def confirm(self):
        name = self.name_text_edit.text().strip()
        v = self.target_version_dial.value()
        major = int(v)
        minor = int((v % 1) * 10)

        target_version = Version(major, minor, 0)
        config_name = config_path_name(name)

        info = ConfigInfo(get_library_folder() / "config" / config_name, target_version, name)
        # ? Do we need to move this to a task? This should be very fast anyways
        info.write()  # Write the file to disk

        self.config_created.emit(info)
        self.update_state(PreferenceFactoryState.READY)

    @pyqtSlot()
    def install(self):
        self.create_pressed.emit()

    @QtCore.pyqtSlot()
    def ask_remove_from_drive(self):
        self.dlg = DialogWindow(
            parent=self,
            title="Warning",
            text="Are you sure you want to<br> \
                  delete these preferences?<br> \
                  Any blender version using these will<br> \
                  revert to the default.",
            accept_text="Yes",
            cancel_text="No",
        )

        if len(self.list_widget.selectedItems()) > 1:
            self.dlg.accepted.connect(self.remove_from_drive_extended)
        else:
            self.dlg.accepted.connect(self.remove_from_drive)
