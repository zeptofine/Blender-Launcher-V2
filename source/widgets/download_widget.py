import re
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from modules.build_info import BuildInfo, ReadBuildAction
from modules.enums import MessageType
from modules.settings import get_install_template, get_library_folder
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from threads.downloader import DownloadAction
from threads.extractor import ExtractAction
from threads.renamer import RenameAction
from threads.template_installer import TemplateAction
from widgets.base_build_widget import BaseBuildWidget
from widgets.base_progress_bar_widget import BaseProgressBarWidget
from widgets.build_state_widget import BuildStateWidget
from widgets.datetime_widget import DateTimeWidget
from widgets.elided_text_label import ElidedTextLabel

if TYPE_CHECKING:
    from windows.main_window import BlenderLauncher


class DownloadState(Enum):
    IDLE = 1
    DOWNLOADING = 2
    EXTRACTING = 3
    READING = 4
    RENAMING = 5


class DownloadWidget(BaseBuildWidget):
    def __init__(self, parent: "BlenderLauncher", list_widget, item, build_info, is_installed, show_new=False):
        super().__init__(parent=parent)
        self.parent: "BlenderLauncher" = parent
        self.list_widget = list_widget
        self.item = item
        self.build_info = build_info
        self.show_new = show_new
        self.is_installed = is_installed
        self.state = DownloadState.IDLE
        self.build_dir = None
        self.source_file = None

        self.progressBar = BaseProgressBarWidget()
        self.progressBar.setFont(self.parent.font_8)
        self.progressBar.setFixedHeight(18)
        self.progressBar.hide()

        self.downloadButton = QPushButton("Download")
        self.downloadButton.setFixedWidth(85)
        self.downloadButton.setProperty("LaunchButton", True)
        self.downloadButton.clicked.connect(self.init_downloader)
        self.downloadButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.installedButton = QPushButton("Installed")
        self.installedButton.setFixedWidth(85)
        self.installedButton.setProperty("InstalledButton", True)

        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.setFixedWidth(85)
        self.cancelButton.setProperty("CancelButton", True)
        self.cancelButton.clicked.connect(self.download_cancelled)
        self.cancelButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancelButton.hide()

        self.main_hl = QHBoxLayout()
        self.main_hl.setContentsMargins(2, 2, 0, 2)
        self.main_hl.setSpacing(0)

        self.sub_vl = QVBoxLayout()
        self.sub_vl.setContentsMargins(0, 0, 0, 0)
        self.main_hl.setSpacing(0)

        self.build_info_hl = QHBoxLayout()
        self.build_info_hl.setContentsMargins(0, 0, 0, 0)
        self.main_hl.setSpacing(0)

        self.progress_bar_hl = QHBoxLayout()
        self.progress_bar_hl.setContentsMargins(16, 0, 8, 0)
        self.main_hl.setSpacing(0)

        if self.build_info.branch == "lts":
            branch_name = "LTS"
        elif self.build_info.branch == "daily":
            branch_name = self.build_info.subversion.split(" ", 1)[-1].title()
        else:
            branch_name = self.build_info.subversion.split(" ", 1)[-1]
            # branch_name = re.sub(
            #     r"(\-|\_)", " ", self.build_info.branch).title()

        self.subversionLabel = QLabel(self.build_info.subversion.split(" ", 1)[0])
        self.subversionLabel.setFixedWidth(85)
        self.subversionLabel.setIndent(20)
        self.branchLabel = ElidedTextLabel(branch_name)
        self.commitTimeLabel = DateTimeWidget(self.build_info.commit_time, self.build_info.build_hash)
        self.build_state_widget = BuildStateWidget(parent, self.list_widget)

        self.build_info_hl.addWidget(self.subversionLabel)
        self.build_info_hl.addWidget(self.branchLabel, stretch=1)
        self.build_info_hl.addWidget(self.commitTimeLabel)

        if self.show_new and not self.is_installed:
            self.build_state_widget.setNewBuild(True)

        self.progress_bar_hl.addWidget(self.progressBar)

        self.sub_vl.addLayout(self.build_info_hl)
        self.sub_vl.addLayout(self.progress_bar_hl)

        if self.is_installed:
            self.downloadButton.hide()
            self.main_hl.addWidget(self.installedButton)
            self.main_hl.addLayout(self.sub_vl)
            self.main_hl.addWidget(self.build_state_widget)
        else:
            self.main_hl.addWidget(self.downloadButton)
            self.main_hl.addWidget(self.cancelButton)
            self.main_hl.addLayout(self.sub_vl)
            self.main_hl.addWidget(self.build_state_widget)

        self.setLayout(self.main_hl)

        if self.build_info.branch in "stable lts":
            self.menu.addAction(self.showReleaseNotesAction)
        else:
            regexp = re.compile(r"D\d{5}")

            if regexp.search(self.build_info.branch):
                self.showReleaseNotesAction.setText("Show Patch Details")
                self.menu.addAction(self.showReleaseNotesAction)

    def context_menu(self):
        self.menu.trigger()

    def mouseDoubleClickEvent(self, event):
        if self.state != DownloadState.DOWNLOADING and not self.is_installed:
            self.init_downloader()

    def mouseReleaseEvent(self, event):
        if self.show_new is True:
            self.build_state_widget.setNewBuild(False)
            self.show_new = False

    def init_downloader(self):
        self.item.setSelected(True)

        if self.show_new is True:
            self.build_state_widget.setNewBuild(False)
            self.show_new = False

        assert self.parent.manager is not None
        self.state = DownloadState.DOWNLOADING
        self.progressBar.set_title("Downloading")
        self.dl_action = DownloadAction(
            manager=self.parent.manager,
            link=self.build_info.link,
        )
        self.dl_action.progress.connect(self.progressBar.set_progress)
        self.dl_action.finished.connect(self.init_extractor)
        self.parent.action_queue.append(self.dl_action)
        self.download_started()

    def init_extractor(self, source):
        self.state = DownloadState.EXTRACTING
        self.progressBar.set_title("Extracting")
        self.build_state_widget.setExtract()

        self.cancelButton.setEnabled(False)
        library_folder = Path(get_library_folder())

        if self.build_info.branch in ("stable", "lts"):
            dist = library_folder / "stable"
        elif self.build_info.branch == "daily":
            dist = library_folder / "daily"
        else:
            dist = library_folder / "experimental"

        self.source_file = source
        a = ExtractAction(file=source, destination=dist)
        a.progress.connect(self.progressBar.set_progress)
        a.finished.connect(self.init_template_installer)
        self.parent.action_queue.append(a)

    def init_template_installer(self, dist: Path):
        self.build_state_widget.setExtract(False)
        self.build_dir = dist

        if get_install_template():
            self.progressBar.set_title("Copying data...")
            a = TemplateAction(destination=self.build_dir)
            a.finished.connect(self.download_get_info)
            self.parent.action_queue.append(a)
        else:
            self.download_get_info()

    def download_started(self):
        self.progressBar.show()
        self.cancelButton.show()
        self.downloadButton.hide()
        self.build_state_widget.setDownload()

    def download_cancelled(self):
        self.item.setSelected(True)
        self.state = DownloadState.IDLE
        self.progressBar.hide()
        self.cancelButton.hide()
        if not self.parent.kill_thread_with_action(self.dl_action):  # killing failed
            self.parent.action_queue.remove(self.dl_action)
        self.downloadButton.show()
        self.build_state_widget.setDownload(False)

    def download_get_info(self):
        self.state = DownloadState.READING
        if self.parent.platform == "Linux":
            archive_name = Path(self.build_info.link).with_suffix("").stem
        else:
            archive_name = Path(self.build_info.link).stem

        assert self.build_dir is not None
        a = ReadBuildAction(
            self.build_dir,
            archive_name=archive_name,
        )
        a.finished.connect(self.download_rename)
        a.failure.connect(lambda: print("Reading failed"))
        self.parent.action_queue.append(a)

    def download_rename(self, build_info: BuildInfo):
        self.state = DownloadState.RENAMING
        new_name = f"blender-{build_info.subversion}+{build_info.branch}.{build_info.build_hash}"
        assert self.build_dir is not None
        a = RenameAction(
            src=self.build_dir,
            dst_name=new_name,
        )
        a.finished.connect(self.download_finished)
        a.failure.connect(lambda: print("Renaming failed"))
        self.parent.action_queue.append(a)

    def download_finished(self, path):
        self.state = DownloadState.IDLE

        if path is None:
            path = self.build_dir

        if path is not None:
            self.parent.draw_to_library(path, True)

            assert self.source_file is not None
            self.parent.clear_temp(self.source_file)

            name = f"{self.subversionLabel.text()} {self.branchLabel.text} {self.build_info.commit_time}"
            self.parent.show_message(
                f"Blender {name} download finished!",
                message_type=MessageType.DOWNLOADFINISHED,
            )
            self.setInstalled()

        self.build_state_widget.setExtract(False)

    def setInstalled(self):
        if self.state == DownloadState.IDLE:
            self.downloadButton.hide()
            self.cancelButton.hide()
            self.progressBar.hide()
            self.main_hl.insertWidget(0, self.installedButton)  # Add installedButton at the beginning
            self.is_installed = True
