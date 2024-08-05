from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from items.enablable_list_widget_item import EnablableListWidgetItem
from modules.blendfile_reader import BlendfileHeader, read_blendfile_header
from modules.build_info import BuildInfo, LaunchOpenLast, LaunchWithBlendFile, launch_build
from modules.settings import (
    get_favorite_path,
    get_launch_timer_duration,
    get_version_specific_queries,
    set_version_specific_queries,
)
from modules.tasks import TaskQueue
from modules.version_matcher import VALID_QUERIES, BasicBuildInfo, BInfoMatcher, VersionSearchQuery
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
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

if TYPE_CHECKING:
    from datetime import datetime


class LaunchingWindow(BaseWindow):
    def __init__(
        self,
        app: QApplication,
        version_query: VersionSearchQuery | None = None,
        blendfile: Path | None = None,
        open_last: bool = False,
    ):
        super().__init__(app=app)
        self.resize(360, 480)

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

        # Get all available versions of Blender
        self.builds: dict[str, BuildInfo] = {}
        self.list_items: dict[str, EnablableListWidgetItem] = {}
        self.drawing_task = DrawLibraryTask()
        self.drawing_task.found.connect(self._build_found)
        self.drawing_task.finished.connect(self.search_finished)
        self.task_queue.append(self.drawing_task)

        self.launch_timer = QTimer(self)
        self.launch_timer.setSingleShot(True)
        self.launch_timer.setInterval(1000)  # 1 second
        self.launch_timer.timeout.connect(self.timer_tick)
        self.launch_timer_duration = get_launch_timer_duration()
        self.remaining_time = self.launch_timer_duration
        self.timer_label = QLabel("", parent=self)
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cancelled = False

        self.launch_button = QPushButton("Launch", parent=self)
        self.launch_button.setProperty("LaunchButton", True)
        self.launch_button.clicked.connect(self.launch_from_button)

        self.cancel_button = QPushButton("Cancel", parent=self)
        self.cancel_button.setProperty("CancelButton", True)
        self.cancel_button.clicked.connect(self.close_)

        ### LAYOUT ###
        widget = QWidget(self)
        self.central_layout = QGridLayout(widget)
        self.central_layout.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(widget)

        self.status_label = QLabel("Reading builds...", parent=self)

        self.help_label = QLabel("?", parent=self)
        self.help_label.setToolTip(
            "<br>".join(
                [
                    "The version query",
                    "can be modified to use ^ and - to search for specific builds depending on age.",
                    "Examples of valid version queries:",
                    *VALID_QUERIES.splitlines(),
                ]
            )
        )
        ## Version settings
        self.version_query_edit = LintableLineEdit(self)
        self.version_query_edit.editingFinished.connect(self.update_query_from_edits)
        self.version_query_edit.textChanged.connect(self.cancel_timer)
        self.version_query_edit.setPlaceholderText("Any (*.*.*)")
        self.branch_edit = LintableLineEdit(self)
        self.branch_edit.editingFinished.connect(self.update_query_from_edits)
        self.branch_edit.textChanged.connect(self.cancel_timer)
        self.branch_edit.setPlaceholderText("Any (*)")
        self.build_hash_edit = LintableLineEdit(self)
        self.build_hash_edit.editingFinished.connect(self.update_query_from_edits)
        self.build_hash_edit.textChanged.connect(self.cancel_timer)
        self.build_hash_edit.setPlaceholderText("Any (*)")
        self.date_range_combo = QComboBox(self)
        self.date_range_combo.addItems(["Latest (^)", "Any (*)", "Oldest (-)"])
        self.date_range_combo.setCurrentIndex(0)
        self.date_range_combo.currentIndexChanged.connect(self.update_query_from_edits)
        self.error_preview = QLabel(self)

        if self.blendfile is not None:
            self.save_current_query_button = QPushButton("Save current query for ???", self)
            self.save_current_query_button.clicked.connect(self.save_current_query)
            self.save_current_query_button.setProperty("CreateButton", True)
        else:
            self.save_current_query_button = None

        if self.version_query is not None:
            self.update_query_boxes(self.version_query)

        self.builds_list = QListWidget(self)
        self.builds_list.itemSelectionChanged.connect(self.cancel_timer)
        self.builds_list.itemDoubleClicked.connect(self.set_query_from_selected_build)

        self.central_layout.addWidget(self.status_label, 0, 1, 1, 2)
        self.central_layout.addWidget(self.help_label, 0, 0, 1, 1)
        self.central_layout.addWidget(QLabel("Version selection: ", parent=self), 1, 0, 1, 1)
        self.central_layout.addWidget(self.version_query_edit, 1, 1, 1, 2)
        self.central_layout.addWidget(QLabel("Branch: ", parent=self), 2, 0, 1, 1)
        self.central_layout.addWidget(self.branch_edit, 2, 1, 1, 2)
        self.central_layout.addWidget(QLabel("Build hash: ", parent=self), 3, 0, 1, 1)
        self.central_layout.addWidget(self.build_hash_edit, 3, 1, 1, 2)
        self.central_layout.addWidget(QLabel("Date selection: ", parent=self), 4, 0, 1, 1)
        self.central_layout.addWidget(self.date_range_combo, 4, 1, 1, 2)
        self.central_layout.addWidget(self.error_preview, 5, 0, 1, 3)
        self.central_layout.addWidget(self.builds_list, 6, 0, 1, 3)
        self.central_layout.addWidget(self.timer_label, 7, 0, 1, 3)
        if self.save_current_query_button is not None:
            self.central_layout.addWidget(self.save_current_query_button, 8, 0, 1, 3)
        self.central_layout.addWidget(self.cancel_button, 9, 0, 1, 1)
        self.central_layout.addWidget(self.launch_button, 9, 1, 1, 2)

        self.__enabled_font = QFont(self.font_10)
        self.__enabled_font.setBold(True)
        self.__enabled_font.setWeight(500)
        self.__disabled_font = QFont(self.font_8)
        self.__disabled_font.setItalic(True)

    @pyqtSlot()
    def update_query_from_edits(self, update_actual_query=True):
        self.ready = False
        txt = self.version_query_edit.text()
        if txt == "":
            txt = "*.*.*"

        branch = self.branch_edit.text()
        if branch == "":
            branch = None

        build_hash = self.build_hash_edit.text()
        if build_hash == "":
            build_hash = None

        print(f"HASH: {build_hash}")
        date_range_choice = self.date_range_combo.currentIndex()

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

    def update_query_boxes(self, query: VersionSearchQuery):
        print("Updating query boxes...")

        self.version_query_edit.setText(f"{query.major}.{query.minor}.{query.patch}")
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
            self.update_query_boxes(vsq)
            self.update_query_from_edits()
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
        branch = info.branch
        version = str(info.subversion)
        custom_name = info.custom_name
        commit_time = str(info.commit_time)

        # Remove Time Zone from commit time
        commit_time = commit_time.rsplit("+")[0]

        # Use Version name for the Branch name and remove it from the version string
        version_name = ["Alpha", "Beta", "Release Candidate"]
        
        for name in version_name:
            if branch.lower() == "daily" and name.lower() in version.lower():
                branch = name
                version = version.lower().replace(name.lower(), "")
            if name.lower() in version.lower():
                version = version.lower().replace(name.lower(), "")
        
        if branch.lower() == "lts":
            branch = branch.upper()
        
        # Capitalize the branch name
        if branch and not branch[0].isupper():
            branch = branch.capitalize()
        
        # Use the custom name if it exists
        if custom_name:
            branch = custom_name

        return f"{version} {branch} {commit_time}"

    @pyqtSlot()
    def search_finished(self):
        self.status_label.setText(f"Found {len(self.builds)} builds")

        # Use quick launch if it exists
        if self.version_query is None and self.blendfile is None and (path := get_favorite_path()):
            for version, build in self.builds.items():
                if build.link == path:
                    self.list_items[version].setSelected(True)
                    self.set_query_from_selected_build()

        self.matcher = self.make_matcher()

        all_queries = get_version_specific_queries()

        if self.version_query is not None:  # then it was given via the CLI
            self.update_query_boxes(self.version_query)

        if self.blendfile is not None and self.blendfile.exists():  # check the blendfile's target version
            header = read_blendfile_header(self.blendfile)
            print(header)
            if header is None:
                raise
            self.saved_header = header
            self.status_label.setText(f"Detected header version: {header.version}")
            if self.save_current_query_button is not None:
                self.save_current_query_button.setText(f"Save current query for {self.saved_header.version} blendfiles")

            v = header.version

            if v in all_queries:
                self.version_query = all_queries[v]
                self.update_query_boxes(self.version_query)
            else:
                vsq = VersionSearchQuery(v.major, v.minor, "^")
                if self.version_query is None:
                    self.update_query_boxes(vsq)

        # Update query with the default settings
        self.update_query_from_edits()

        matches, builds = self.update_search()
        # If there's only one match, start a launch timer
        if self.launch_timer_duration != -1 and len(matches) == 1:
            self.ready = True
            build = builds[0]
            self.list_items[self.__version_url(build)].setSelected(True)
            print(matches)

            if self.launch_timer_duration == 0: # launch immediately
                self.actually_launch(build)
            else:
                self.prepare_launch(build)

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

        if len(versions) != 1:
            self.launch_button.setEnabled(False)
        else:
            self.launch_button.setEnabled(True)

        self.builds_list.sortItems(Qt.SortOrder.DescendingOrder)

        return matches, enabled_builds

    @pyqtSlot()
    def save_current_query(self):
        """Saves the current query for the given header version to the settings."""
        if self.saved_header is not None and self.version_query is not None:
            all_matchers = get_version_specific_queries()
            all_matchers[self.saved_header.version] = self.version_query
            set_version_specific_queries(all_matchers)

    def launch_from_button(self):
        """Launches the currently selected build from the list of enabled builds."""
        _, binfos = self.update_search()
        assert len(binfos) == 1
        build = binfos[0]
        self.actually_launch(build)

    def prepare_launch(self, build: BuildInfo):
        """Prepares the given build for launching, starts the timer."""
        self.timer_label.setText(f"Launching in {self.remaining_time}s")
        self.launch_timer.start()
        self.target_build = build

    @pyqtSlot()
    def timer_tick(self):
        """Called by the launch timer waiting to start the build."""
        self.remaining_time = self.remaining_time - 1
        if self.remaining_time > 0:
            self.timer_label.setText(f"Launching in {self.remaining_time}s")
            self.launch_timer.start()
        else:
            self.actually_launch(self.target_build)

    @pyqtSlot()
    def cancel_timer(self):
        """Stops the launch timer."""
        self.timer_label.setText("")
        self.launch_timer.stop()

        # disconnect signals to avoid constant updates. this function should only be called ~once
        if self.cancelled:
            self.version_query_edit.textChanged.disconnect(self.cancel_timer)
            self.branch_edit.textChanged.disconnect(self.cancel_timer)
            self.build_hash_edit.textChanged.disconnect(self.cancel_timer)
            self.builds_list.itemSelectionChanged.disconnect(self.cancel_timer)
            self.cancelled = True

    def actually_launch(self, build: BuildInfo):
        # find an appropriate launch mode
        launch_mode = None
        if self.blendfile is not None:
            launch_mode = LaunchWithBlendFile(self.blendfile)
        if self.open_last:
            launch_mode = LaunchOpenLast()

        launch_build(info=build, launch_mode=launch_mode)

        self.close()

    @pyqtSlot()
    def close_(self):
        """Close slot for cancel button"""
        self.close()

    def closeEvent(self, e):
        self.task_queue.fullstop()
        e.accept()
