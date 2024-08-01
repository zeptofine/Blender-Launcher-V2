from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path

from modules.blendfile_reader import read_blendfile_header
from modules.build_info import BuildInfo, LaunchOpenLast, LaunchWithBlendFile, launch_build
from modules.tasks import TaskQueue
from modules.version_matcher import BasicBuildInfo, BInfoMatcher, VersionSearchQuery
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from threads.library_drawer import DrawLibraryTask
from widgets.lintable_line_edit import LintableLineEdit
from windows.base_window import BaseWindow


class LaunchingWindow(BaseWindow):
    def __init__(
        self,
        app: QApplication,
        version_query: VersionSearchQuery | None = None,
        blendfile: Path | None = None,
        open_last: bool = False,
    ):
        super().__init__(app=app)
        self.resize(480, 480)

        # task queue
        self.task_queue = TaskQueue(
            worker_count=1,
            parent=self,
        )
        self.task_queue.start()

        self.version_query = version_query
        self.blendfile = blendfile
        self.open_last = open_last

        # if the window is ready to launch a specific version of Blender
        self.ready = False

        # Get all available versions of Blender
        self.builds: dict[str, BuildInfo] = {}
        self.list_items: dict[str, EnablableListWidgetItem] = {}
        self.drawing_task = DrawLibraryTask()
        self.drawing_task.found.connect(self._build_found)
        self.drawing_task.finished.connect(self.search_finished)
        self.task_queue.append(self.drawing_task)

        ### LAYOUT ###
        widget = QWidget(self)
        self.central_layout = QGridLayout(widget)
        self.central_layout.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(widget)

        self.status_label = QLabel("Reading builds...", parent=self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.central_layout.addWidget(self.status_label, 0, 0, 1, 2)


        self.version_query_edit = LintableLineEdit(self)
        self.version_query_edit.textChanged.connect(self.query_edit_changed)
        self.__enabled_font = QFont(self.font_10)
        self.__enabled_font.setBold(True)
        self.__enabled_font.setWeight(500)
        self.__disabled_font = QFont(self.font_8)
        self.__disabled_font.setItalic(True)

        self.central_layout.addWidget(QLabel("Version selection: ", parent=self), 1, 0)
        self.central_layout.addWidget(self.version_query_edit, 1, 1)
        if self.version_query is not None:
            self.version_query_edit.setText(str(self.version_query))

        self.builds_list = QListWidget(self)
        self.central_layout.addWidget(self.builds_list, 2, 0, 1, 2)


    def query_edit_changed(self):
        txt = self.version_query_edit.text()
        try:
            self.version_query = VersionSearchQuery.parse(txt)
            self.version_query_edit.set_valid(True)
            self.update_search_query()
        except ValueError:
            self.version_query_edit.set_valid(False)

    @pyqtSlot(Path)
    def _build_found(self, pth: Path):
        # read the build info file and add it to the list
        if (blinfo := pth / ".blinfo").exists():
            with blinfo.open("r", encoding="utf-8") as f:
                blinfo = json.load(f)
            with contextlib.suppress(Exception):
                info = BuildInfo.from_dict(str(pth), blinfo["blinfo"][0])

                semversion = self.__version_url(info)

                item = EnablableListWidgetItem(
                    enabled_font=self.__enabled_font,
                    disable_font=self.__disabled_font,
                    parent=self.builds_list,
                )
                item.setText(semversion)

                self.builds[semversion] = info
                self.list_items[semversion] = item

    @staticmethod
    def __version_url(info: BuildInfo) -> str:
        return f"{Path(info.link).parent.stem}/{info.full_semversion}"

    @pyqtSlot()
    def search_finished(self):
        self.status_label.setText(f"Found {len(self.builds)} builds")

        if self.version_query is None and self.blendfile is None:  # Launch quick launch if it exists
            for version, build in self.builds.items():
                if build.is_favorite:
                    # TODO: prioritize this build somehow?
                    break

        self.matcher = self.make_matcher()

        if self.blendfile is not None:  # check the blendfile's target version
            header = read_blendfile_header(self.blendfile)
            print(header)
            if header is None:
                raise
            # create an initial search query
            v = header.version

            vsq = VersionSearchQuery(v.major, v.minor, "^")
            if self.version_query is None:
                self.version_query_edit.setText(str(vsq))
                self.version_query = vsq

            matches, builds = self.update_search_query()
            # check if there's only one match
            if len(matches) == 1:
                self.ready = True
                build = builds[0]
                self.list_items[self.__version_url(build)].setSelected(True)
                print(matches)

        # Depending on the launch mode, figure out what version to launch
        ...

        if self.ready:  # Start timer to launching the selected build
            ...

    def make_matcher(self):
        return BInfoMatcher(tuple(map(BasicBuildInfo.from_buildinfo, self.builds.values())))

    def update_search_query(self) -> tuple[tuple[BasicBuildInfo, ...], list[BuildInfo]]:
        """Updates the visibility of each item in the list depending on the search query. returns matches"""
        print("Updating...")
        assert self.version_query is not None
        matcher = self.make_matcher()
        matches = matcher.match(self.version_query)
        versions = {b.version for b in matches}

        enabled_builds: list[BuildInfo] = []

        for version, build in self.builds.items():
            print(version, build)
            item = self.list_items[version]

            item.enabled = build.full_semversion in versions
            if item.enabled:
                enabled_builds.append(build)
            print(item.enabled)

        self.builds_list.sortItems(Qt.SortOrder.DescendingOrder)

        return matches, enabled_builds

    def closeEvent(self, e):
        self.task_queue.fullstop()
        e.accept()


class EnablableListWidgetItem(QListWidgetItem):
    def __init__(self, enabled_font: QFont, disable_font: QFont, parent=None):
        super().__init__(parent)
        self._enabled = True
        self.__enabled_font = enabled_font
        self.__disable_font = disable_font

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value
        if value:
            self.setFont(self.__enabled_font)
        else:
            self.setFont(self.__disable_font)

    def __lt__(self, other: EnablableListWidgetItem):
        return self.enabled < other.enabled
