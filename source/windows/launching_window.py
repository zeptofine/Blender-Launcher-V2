from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from items.enablable_list_widget_item import EnablableListWidgetItem
from modules.blendfile_reader import BlendfileHeader, read_blendfile_header
from modules.build_info import BuildInfo, LaunchOpenLast, LaunchWithBlendFile, launch_build
from modules.tasks import TaskQueue
from modules.version_matcher import BasicBuildInfo, BInfoMatcher, VersionSearchQuery
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDateTimeEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
        self.saved_header: BlendfileHeader | None = None
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
        self.central_layout.addWidget(self.status_label, 0, 0, 1, 3)

        ## Version settings
        self.version_query_edit = LintableLineEdit(self)
        self.version_query_edit.editingFinished.connect(self.update_query_from_edits)
        self.branch_edit = LintableLineEdit(self)
        self.branch_edit.editingFinished.connect(self.update_query_from_edits)
        self.branch_edit.setPlaceholderText("Any (*)")
        self.build_hash_edit = LintableLineEdit(self)
        self.build_hash_edit.editingFinished.connect(self.update_query_from_edits)
        self.build_hash_edit.setPlaceholderText("Any (*)")
        self.date_range_combo = QComboBox(self)
        self.date_range_combo.addItems(["Latest (^)", "Any (*)", "Oldest (-)"])
        self.date_range_combo.setCurrentIndex(0)
        self.date_range_combo.currentIndexChanged.connect(self.update_query_from_edits)
        self.error_preview = QLabel(self)

        self.date_range_combo.currentIndexChanged.emit(0)

        self.central_layout.addWidget(QLabel("Version selection: ", parent=self), 1, 0, 1, 1)
        self.central_layout.addWidget(self.version_query_edit, 1, 1, 1, 2)
        self.central_layout.addWidget(QLabel("Branch: ", parent=self), 2, 0, 1, 1)
        self.central_layout.addWidget(self.branch_edit, 2, 1, 1, 2)
        self.central_layout.addWidget(QLabel("Build hash: ", parent=self), 3, 0, 1, 1)
        self.central_layout.addWidget(self.build_hash_edit, 3, 1, 1, 2)
        self.central_layout.addWidget(QLabel("Date selection: ", parent=self), 4, 0, 1, 1)
        self.central_layout.addWidget(self.date_range_combo, 4, 1, 1, 2)
        self.central_layout.addWidget(self.error_preview, 5, 0, 1, 3)
        if self.version_query is not None:
            self.update_query(self.version_query)

        self.builds_list = QListWidget(self)
        self.builds_list.itemDoubleClicked.connect(self.set_query_from_selected_build)
        self.central_layout.addWidget(self.builds_list, 6, 0, 1, 3)

        self.__enabled_font = QFont(self.font_10)
        self.__enabled_font.setBold(True)
        self.__enabled_font.setWeight(500)
        self.__disabled_font = QFont(self.font_8)
        self.__disabled_font.setItalic(True)

    @pyqtSlot()
    def update_query_from_edits(self, update_actual_query=True):
        self.ready = False
        txt = self.version_query_edit.text()

        branch = self.branch_edit.text()
        if branch == "":
            branch = None

        build_hash = self.build_hash_edit.text()
        if build_hash == "":
            build_hash = None

        date_range_choice = self.date_range_combo.currentIndex()
        date: str | datetime | None = None
        if date_range_choice == 0:  # Latest (^)
            date = "^"
        elif date_range_choice == 1:  # Any (*)
            date = "*"
        elif date_range_choice == 2:  # Oldest (-)
            date = "-"

        if update_actual_query:
            try:
                self.version_query = (
                    VersionSearchQuery.parse(txt).with_branch(branch).with_build_hash(build_hash).with_commit_time(date)
                )
                print(f"Updating query: {self.version_query!r}")
                self.version_query_edit.set_valid(True)
                self.branch_edit.set_valid(True)
                self.build_hash_edit.set_valid(True)
                self.update_search()
                self.error_preview.setText("")
            except ValueError as e:
                self.version_query_edit.set_valid(False)
                self.branch_edit.set_valid(False)
                self.build_hash_edit.set_valid(False)
                self.error_preview.setText(str(e))

    def update_query(self, query: VersionSearchQuery):
        print(f"Updating query: {query!r}")
        self.version_query = query

        self.version_query_edit.setText(str(query))
        self.branch_edit.setText(query.branch or "")
        self.build_hash_edit.setText(query.build_hash or "")

    def set_query_from_selected_build(self):
        items = self.builds_list.selectedItems()
        if len(items) == 1:  # get build info from the item and set it as the query
            text = items[0].text()
            build = self.builds[text]
            version = build.full_semversion

            vsq = VersionSearchQuery(
                major=version.major,
                minor=version.minor,
                patch=version.patch,
                branch=build.branch,
                build_hash=build.build_hash,
                commit_time=build.commit_time,
            )
            self.update_query(vsq)
            self.update_search()

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
                    build=info,
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
                    self.list_items[version].setSelected(True)
                    self.set_query_from_selected_build()

        self.matcher = self.make_matcher()

        if self.blendfile is not None:  # check the blendfile's target version
            header = read_blendfile_header(self.blendfile)
            print(header)
            if header is None:
                raise
            self.saved_header = header
            # create an initial search query
            v = header.version

            vsq = VersionSearchQuery(v.major, v.minor, "^")
            if self.version_query is None:
                self.version_query_edit.setText(str(vsq))

            # Update query with the default settings
            self.update_query_from_edits()

            matches, builds = self.update_search()
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

    def update_search(self) -> tuple[tuple[BasicBuildInfo, ...], list[BuildInfo]]:
        """Updates the visibility of each item in the list depending on the search query. returns matches"""
        assert self.version_query is not None
        print(f"QUERY: {self.version_query!r}")
        matcher = self.make_matcher()
        matches = matcher.match(self.version_query)
        versions = {b.version for b in matches}

        enabled_builds: list[BuildInfo] = []

        for version, build in self.builds.items():
            item = self.list_items[version]

            item.enabled = build.full_semversion in versions
            if item.enabled:
                enabled_builds.append(build)

        self.builds_list.sortItems(Qt.SortOrder.DescendingOrder)

        return matches, enabled_builds

    def closeEvent(self, e):
        self.task_queue.fullstop()
        e.accept()
