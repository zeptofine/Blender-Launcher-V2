from __future__ import annotations

import logging
import os
import re
import webbrowser
from enum import Enum
from functools import partial
from pathlib import Path
from platform import version
from shutil import copyfileobj
from time import localtime, strftime
from typing import TYPE_CHECKING

import resources_rc
from items.base_list_widget_item import BaseListWidgetItem
from modules._platform import _popen, get_cwd, get_platform, is_frozen, set_locale
from modules.connection_manager import ConnectionManager
from modules.enums import MessageType
from modules.settings import (
    create_library_folders,
    get_default_downloads_page,
    get_default_library_page,
    get_default_preferences_tab,
    get_default_tab,
    get_enable_download_notifications,
    get_enable_new_builds_notifications,
    get_enable_quick_launch_key_seq,
    get_launch_minimized_to_tray,
    get_library_folder,
    get_make_error_popup,
    get_proxy_type,
    get_quick_launch_key_seq,
    get_show_tray_icon,
    get_sync_library_and_downloads_pages,
    get_worker_thread_count,
    is_library_folder_valid,
    set_library_folder,
)
from modules.tasks import Task, TaskQueue, TaskWorker
from pynput import keyboard
from PyQt5.QtCore import QSize, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtNetwork import QLocalServer
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QLabel,
    QPushButton,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from threads.library_drawer import DrawLibraryTask
from threads.remover import RemovalTask
from threads.scraper import Scraper
from widgets.base_menu_widget import BaseMenuWidget
from widgets.base_page_widget import BasePageWidget
from widgets.base_tool_box_widget import BaseToolBoxWidget
from widgets.download_widget import DownloadState, DownloadWidget
from widgets.foreign_build_widget import UnrecoBuildWidget
from widgets.header import WHeaderButton, WindowHeader
from widgets.library_widget import LibraryWidget
from widgets.preference_factory_widget import PreferenceFactoryWidget
from windows.base_window import BaseWindow
from windows.dialog_window import DialogIcon, DialogWindow
from windows.file_dialog_window import FileDialogWindow
from windows.settings_window import SettingsWindow

if TYPE_CHECKING:
    from PyQt5.QtGui import QDragEnterEvent, QDragMoveEvent
    from widgets.base_build_widget import BaseBuildWidget

if get_platform() == "Windows":
    from PyQt5.QtWinExtras import QWinThumbnailToolBar, QWinThumbnailToolButton

logger = logging.getLogger()


class AppState(Enum):
    IDLE = 1
    CHECKINGBUILDS = 2


class BlenderLauncher(BaseWindow):
    show_signal = pyqtSignal()
    close_signal = pyqtSignal()
    quit_signal = pyqtSignal()
    quick_launch_fail_signal = pyqtSignal()

    def __init__(self, app: QApplication, version, argv):
        super().__init__(app=app, version=version)
        self.resize(640, 480)
        self.setMinimumSize(QSize(640, 480))
        self.setMaximumSize(QSize(1024, 768))
        widget = QWidget(self)
        self.CentralLayout = QVBoxLayout(widget)
        self.CentralLayout.setContentsMargins(1, 1, 1, 1)
        self.setCentralWidget(widget)
        self.setAcceptDrops(True)

        # Server
        self.server = QLocalServer()
        self.server.listen("blender-launcher-server")
        self.quick_launch_fail_signal.connect(self.quick_launch_fail)
        self.server.newConnection.connect(self.new_connection)

        # task queue
        self.task_queue = TaskQueue(
            worker_count=get_worker_thread_count(),
            parent=self,
            on_spawn=self.on_worker_creation,
        )
        self.task_queue.start()
        self.quit_signal.connect(self.task_queue.fullstop)

        # Global scope
        self.app = app
        self.version = version
        self.argv = argv
        self.favorite: BaseBuildWidget | None = None
        self.status = "Unknown"
        self.is_force_check_on = False
        self.app_state = AppState.IDLE
        self.cashed_builds = []
        self.notification_pool = []
        self.windows = [self]
        self.timer = None
        self.started = True
        self.latest_tag = ""
        self.new_downloads = False
        self.platform = get_platform()
        self.settings_window = None
        self.hk_listener = None

        if self.platform == "macOS":
            self.app.aboutToQuit.connect(self._aboutToQuit)

        # Setup window
        self.setWindowTitle("Blender Launcher")
        self.app.setWindowIcon(self.icons.taskbar)

        # Set library folder from command line arguments
        if "-set-library-folder" in self.argv:
            library_folder = self.argv[-1]

            if set_library_folder(library_folder) is True:
                create_library_folders(get_library_folder())
                self.draw(True)
            else:
                self.dlg = DialogWindow(
                    parent=self,
                    title="Warning",
                    text="Passed path is not a valid folder or<br>\
                    it doesn't have write permissions!",
                    accept_text="Quit",
                    cancel_text=None,
                )
                self.dlg.accepted.connect(self.app.quit)

            return

        # Check library folder
        if is_library_folder_valid() is False:
            self.dlg = DialogWindow(
                parent=self,
                title="Setup",
                text="First, choose where Blender<br>builds will be stored",
                accept_text="Continue",
                cancel_text=None,
                icon=DialogIcon.INFO,
            )
            self.dlg.accepted.connect(self.set_library_folder)
        else:
            create_library_folders(get_library_folder())
            self.draw()

    def set_library_folder(self):
        library_folder = get_cwd().as_posix()
        new_library_folder = FileDialogWindow().get_directory(self, "Select Library Folder", library_folder)

        if new_library_folder:
            if set_library_folder(new_library_folder) is True:
                self.draw(True)
            else:
                self.dlg = DialogWindow(
                    parent=self,
                    title="Warning",
                    text="Selected folder is not valid or<br>\
                    doesn't have write permissions!",
                    accept_text="Retry",
                    cancel_text=None,
                )
                self.dlg.accepted.connect(self.set_library_folder)
        else:
            self.app.quit()

    def draw(self, polish=False):
        # Header
        self.SettingsButton = WHeaderButton(self.icons.settings, "", self)
        self.SettingsButton.setToolTip("Show settings window")
        self.SettingsButton.clicked.connect(self.show_settings_window)
        self.DocsButton = WHeaderButton(self.icons.wiki, "", self)
        self.DocsButton.setToolTip("Open documentation")
        self.DocsButton.clicked.connect(self.open_docs)

        self.SettingsButton.setProperty("HeaderButton", True)
        self.DocsButton.setProperty("HeaderButton", True)

        self.header = WindowHeader(
            self,
            "Blender Launcher",
            (
                self.SettingsButton,
                self.DocsButton,
            ),
        )
        self.header.close_signal.connect(self.attempt_close)
        self.header.minimize_signal.connect(self.showMinimized)
        self.CentralLayout.addWidget(self.header)

        # Tab layout
        self.TabWidget = QTabWidget()
        self.TabWidget.setProperty("North", True)
        self.CentralLayout.addWidget(self.TabWidget)

        self.LibraryTab = QWidget()
        self.LibraryTabLayout = QVBoxLayout()
        self.LibraryTabLayout.setContentsMargins(0, 0, 0, 0)
        self.LibraryTab.setLayout(self.LibraryTabLayout)
        self.TabWidget.addTab(self.LibraryTab, "Library")

        self.DownloadsTab = QWidget()
        self.DownloadsTabLayout = QVBoxLayout()
        self.DownloadsTabLayout.setContentsMargins(0, 0, 0, 0)
        self.DownloadsTab.setLayout(self.DownloadsTabLayout)
        self.TabWidget.addTab(self.DownloadsTab, "Downloads")

        self.UserTab = QWidget()
        self.UserTabLayout = QVBoxLayout()
        self.UserTabLayout.setContentsMargins(0, 0, 0, 0)
        self.UserTab.setLayout(self.UserTabLayout)
        self.TabWidget.addTab(self.UserTab, "User")

        self.PreferencesTab = QWidget()
        self.PreferencesTabLayout = QVBoxLayout()
        self.PreferencesTabLayout.setContentsMargins(0, 0, 0, 0)
        self.PreferencesTab.setLayout(self.PreferencesTabLayout)
        self.TabWidget.addTab(self.PreferencesTab, "Preferences")

        self.LibraryToolBox = BaseToolBoxWidget(self)
        self.DownloadsToolBox = BaseToolBoxWidget(self)
        self.UserToolBox = BaseToolBoxWidget(self)
        self.PreferencesToolBox = BaseToolBoxWidget(self)

        self.toggle_sync_library_and_downloads_pages(get_sync_library_and_downloads_pages())

        self.LibraryTabLayout.addWidget(self.LibraryToolBox)
        self.DownloadsTabLayout.addWidget(self.DownloadsToolBox)
        self.UserTabLayout.addWidget(self.UserToolBox)
        self.PreferencesTabLayout.addWidget(self.PreferencesToolBox)

        self.LibraryStablePageWidget = BasePageWidget(
            parent=self,
            page_name="LibraryStableListWidget",
            time_label="Commit Time",
            info_text="Nothing to show yet",
            extended_selection=True,
        )
        self.LibraryStableListWidget = self.LibraryToolBox.add_page_widget(self.LibraryStablePageWidget, "Stable")

        self.LibraryDailyPageWidget = BasePageWidget(
            parent=self,
            page_name="LibraryDailyListWidget",
            time_label="Commit Time",
            info_text="Nothing to show yet",
            extended_selection=True,
        )
        self.LibraryDailyListWidget = self.LibraryToolBox.add_page_widget(self.LibraryDailyPageWidget, "Daily")

        self.LibraryExperimentalPageWidget = BasePageWidget(
            parent=self,
            page_name="LibraryExperimentalListWidget",
            time_label="Commit Time",
            info_text="Nothing to show yet",
            extended_selection=True,
        )
        self.LibraryExperimentalListWidget = self.LibraryToolBox.add_page_widget(
            self.LibraryExperimentalPageWidget, "Experimental"
        )

        self.DownloadsStablePageWidget = BasePageWidget(
            parent=self,
            page_name="DownloadsStableListWidget",
            time_label="Upload Time",
            info_text="No new builds available",
        )
        self.DownloadsStableListWidget = self.DownloadsToolBox.add_page_widget(self.DownloadsStablePageWidget, "Stable")

        self.DownloadsDailyPageWidget = BasePageWidget(
            parent=self,
            page_name="DownloadsDailyListWidget",
            time_label="Upload Time",
            info_text="No new builds available",
        )
        self.DownloadsDailyListWidget = self.DownloadsToolBox.add_page_widget(self.DownloadsDailyPageWidget, "Daily")

        self.DownloadsExperimentalPageWidget = BasePageWidget(
            parent=self,
            page_name="DownloadsExperimentalListWidget",
            time_label="Upload Time",
            info_text="No new builds available",
        )
        self.DownloadsExperimentalListWidget = self.DownloadsToolBox.add_page_widget(
            self.DownloadsExperimentalPageWidget, "Experimental"
        )

        self.UserFavoritesListWidget = BasePageWidget(
            parent=self, page_name="UserFavoritesListWidget", time_label="Commit Time", info_text="Nothing to show yet"
        )
        self.UserFavoritesListWidget = self.UserToolBox.add_page_widget(self.UserFavoritesListWidget, "Favorites")

        self.UserCustomPageWidget = BasePageWidget(
            parent=self,
            page_name="UserCustomListWidget",
            time_label="Commit Time",
            info_text="Nothing to show yet",
            show_reload=True,
            extended_selection=True,
        )
        self.UserCustomListWidget = self.UserToolBox.add_page_widget(self.UserCustomPageWidget, "Custom")

        self.PreferencesPageWidget = BasePageWidget(
            parent=self,
            page_name="PreferencesPageWidget",
            time_label="Commit Time",
            info_text="Nothing to show yet",
            show_reload=True,
            extended_selection=True,
        )
        self.PreferencesListWidget = self.PreferencesToolBox.add_page_widget(self.PreferencesPageWidget, "Versions")

        self.TabWidget.setCurrentIndex(get_default_tab())
        self.LibraryToolBox.setCurrentIndex(get_default_library_page())
        self.DownloadsToolBox.setCurrentIndex(get_default_downloads_page())
        self.PreferencesToolBox.setCurrentIndex(get_default_preferences_tab())

        # Status bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.setContentsMargins(0, 0, 0, 2)
        self.status_bar.setFont(self.font_10)
        self.statusbarLabel = QLabel()
        self.ForceCheckNewBuilds = QPushButton("Check")
        self.ForceCheckNewBuilds.setEnabled(False)
        self.ForceCheckNewBuilds.clicked.connect(self.draw_downloads)
        self.NewVersionButton = QPushButton()
        self.NewVersionButton.hide()
        self.NewVersionButton.clicked.connect(self.show_update_window)
        self.statusbarVersion = QPushButton(self.version)
        self.statusbarVersion.clicked.connect(self.show_changelog)
        self.statusbarVersion.setToolTip(
            "The version of Blender Launcher that is currently run. Press to check changelog."
        )
        self.status_bar.addPermanentWidget(self.ForceCheckNewBuilds)
        self.status_bar.addPermanentWidget(QLabel("│"))
        self.status_bar.addPermanentWidget(self.statusbarLabel)
        self.status_bar.addPermanentWidget(QLabel(""), 1)
        self.status_bar.addPermanentWidget(self.NewVersionButton)
        self.status_bar.addPermanentWidget(self.statusbarVersion)

        # Draw library
        self.draw_library()

        # Draw preferences
        self.draw_preferences_factory()

        # Setup tray icon context Menu
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_)
        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self.attempt_close)
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show)
        show_favorites_action = QAction(self.icons.favorite, "Favorites", self)
        show_favorites_action.triggered.connect(self.show_favorites)
        quick_launch_action = QAction(self.icons.quick_launch, "Blender", self)
        quick_launch_action.triggered.connect(self.quick_launch)

        self.tray_menu = BaseMenuWidget()
        self.tray_menu.setFont(self.font_10)
        self.tray_menu.addActions(
            [
                quick_launch_action,
                show_favorites_action,
                show_action,
                hide_action,
                quit_action,
            ]
        )

        # Setup tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.icons.taskbar)
        self.tray_icon.setToolTip("Blender Launcher")
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.messageClicked.connect(self._show)

        # Linux doesn't handle QSystemTrayIcon.Context activation reason,
        # so add context menu as regular one
        if self.platform == "Linux":
            self.tray_icon.setContextMenu(self.tray_menu)

        # Force style update
        if polish is True:
            style = self.style()
            assert style is not None
            style.unpolish(self.app)
            style.polish(self.app)

        # Show window
        if is_frozen():
            if get_show_tray_icon():
                self.tray_icon.show()

                if get_launch_minimized_to_tray() is False:
                    self._show()
            else:
                self.tray_icon.hide()
                self._show()
        else:
            self.tray_icon.show()
            self._show()

        if get_enable_quick_launch_key_seq() is True:
            self.setup_global_hotkeys_listener()

    def setup_global_hotkeys_listener(self):
        if self.hk_listener is not None:
            self.hk_listener.stop()

        key_seq = get_quick_launch_key_seq()
        keys = key_seq.split("+")

        for key in keys:
            if len(key) > 1:
                key_seq = key_seq.replace(key, "<" + key + ">")

        try:
            self.hk_listener = keyboard.GlobalHotKeys({key_seq: self.on_activate_quick_launch})
        except Exception:
            self.dlg = DialogWindow(
                parent=self,
                title="Warning",
                text="Global hotkey sequence was not recognized!<br>Try to use another combination of keys",
                accept_text="OK",
                cancel_text=None,
            )
            return

        self.hk_listener.start()

    def on_activate_quick_launch(self):
        if self.settings_window is None:
            self.quick_launch()

    def show_changelog(self):
        url = f"https://github.com/Victor-IX/Blender-Launcher-V2/releases/tag/v{self.version}"
        webbrowser.open(url)

    def toggle_sync_library_and_downloads_pages(self, is_sync):
        if is_sync:
            self.LibraryToolBox.tab_changed.connect(self.DownloadsToolBox.setCurrentIndex)
            self.DownloadsToolBox.tab_changed.connect(self.LibraryToolBox.setCurrentIndex)
        else:
            if self.isSignalConnected(self.LibraryToolBox, "tab_changed()"):
                self.LibraryToolBox.tab_changed.disconnect()

            if self.isSignalConnected(self.DownloadsToolBox, "tab_changed()"):
                self.DownloadsToolBox.tab_changed.disconnect()

    def isSignalConnected(self, obj, name):
        index = obj.metaObject().indexOfMethod(name)

        if index > -1:
            method = obj.metaObject().method(index)

            if method:
                return obj.isSignalConnected(method)

        return False

    def is_downloading_idle(self):
        download_widgets = []

        download_widgets.extend(self.DownloadsStableListWidget.items())
        download_widgets.extend(self.DownloadsDailyListWidget.items())
        download_widgets.extend(self.DownloadsExperimentalListWidget.items())

        return all(widget.state == DownloadState.IDLE for widget in download_widgets)

    def show_update_window(self):
        if not self.is_downloading_idle():
            self.dlg = DialogWindow(
                parent=self,
                title="Warning",
                text="In order to update Blender Launcher<br> \
                        complete all active downloads!",
                accept_text="OK",
                cancel_text=None,
            )

            return

        # Create copy if 'Blender Launcher.exe' file
        # to act as an updater program
        if self.platform == "Windows":
            bl_exe = "Blender Launcher.exe"
            blu_exe = "Blender Launcher Updater.exe"
        elif self.platform == "Linux":
            bl_exe = "Blender Launcher"
            blu_exe = "Blender Launcher Updater"

        cwd = get_cwd()
        source = cwd / bl_exe
        dist = cwd / blu_exe

        with open(source.as_posix(), "rb") as f1, open(dist.as_posix(), "wb") as f2:
            copyfileobj(f1, f2)

        # Run 'Blender Launcher Updater.exe' with '-update' flag
        if self.platform == "Windows":
            _popen([dist.as_posix(), "-update", self.latest_tag])
        elif self.platform == "Linux":
            os.chmod(dist.as_posix(), 0o744)
            _popen(f'nohup "{dist.as_posix()}" -update {self.latest_tag}')

        # Destroy currently running Blender Launcher instance
        self.server.close()
        self.destroy()

    def _show(self):
        if self.isMinimized():
            self.showNormal()

        if self.platform == "Windows":
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()
        elif self.platform in {"Linux", "macOS"}:
            self.show()
            self.activateWindow()

        self.set_status()
        self.show_signal.emit()

        # Add custom toolbar icons
        if self.platform == "Windows":
            self.thumbnail_toolbar = QWinThumbnailToolBar(self)
            self.thumbnail_toolbar.setWindow(self.windowHandle())

            self.toolbar_quick_launch_btn = QWinThumbnailToolButton(self.thumbnail_toolbar)
            self.toolbar_quick_launch_btn.setIcon(self.icons.quick_launch)
            self.toolbar_quick_launch_btn.setToolTip("Quick Launch")
            self.toolbar_quick_launch_btn.clicked.connect(self.quick_launch)
            self.thumbnail_toolbar.addButton(self.toolbar_quick_launch_btn)

            self.toolbar_quit_btn = QWinThumbnailToolButton(self.thumbnail_toolbar)
            self.toolbar_quit_btn.setIcon(self.icons.close)
            self.toolbar_quit_btn.setToolTip("Quit")
            self.toolbar_quit_btn.clicked.connect(self.quit_)
            self.thumbnail_toolbar.addButton(self.toolbar_quit_btn)

    def show_message(self, message, value=None, message_type=None):
        if (
            (message_type == MessageType.DOWNLOADFINISHED and not get_enable_download_notifications())
            or (message_type == MessageType.NEWBUILDS and not get_enable_new_builds_notifications())
            or (message_type == MessageType.ERROR and not get_make_error_popup())
        ):
            return

        if value not in self.notification_pool:
            if value is not None:
                self.notification_pool.append(value)
            self.tray_icon.showMessage("Blender Launcher", message, self.icons.taskbar, 10000)

    def message_from_error(self, err: Exception):
        self.show_message(f"An error has occurred: {err}\nSee the logs for more details.", MessageType.ERROR)
        logger.error(err)

    def message_from_worker(self, w, message, message_type=None):
        logger.debug(f"{w} ({message_type}): {message}")
        self.show_message(f"{w}: {message}", message_type)

    @pyqtSlot(TaskWorker)
    def on_worker_creation(self, w: TaskWorker):
        w.error.connect(self.message_from_error)
        w.message.connect(partial(self.message_from_worker, w))

    def show_favorites(self):
        self.TabWidget.setCurrentWidget(self.UserTab)
        self.UserToolBox.setCurrentWidget(self.UserFavoritesListWidget)
        self._show()

    def quick_launch(self):
        try:
            assert self.favorite
            self.favorite.launch()
        except Exception:
            self.quick_launch_fail_signal.emit()

    def quick_launch_fail(self):
        self.dlg = DialogWindow(
            parent=self,
            text="Add build to Quick Launch via<br>\
                        context menu to run it from tray",
            accept_text="OK",
            cancel_text=None,
            icon=DialogIcon.INFO,
        )

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.quick_launch()

        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self.tray_menu.trigger()

    def _aboutToQuit(self):
        self.quit_()

    def quit_(self):
        busy = self.task_queue.get_busy_threads()
        if any(busy):
            self.dlg = DialogWindow(
                parent=self,
                title="Warning",
                text=(
                    "Some tasks are still in progress!<br>"
                    + "\n".join([f" - {item}<br>" for worker, item in busy.items()])
                    + "Are you sure you want to quit?"
                ),
                accept_text="Yes",
                cancel_text="No",
            )

            self.dlg.accepted.connect(self.destroy)
            return

        self.destroy()

    def kill_thread_with_task(self, task: Task):
        """
        Kills a thread listener using the current task

        Arguments:
            task -- Task to search for

        Returns:
            Success.
        """
        thread = self.task_queue.thread_with_task(task)
        if thread is not None:
            thread.fullstop()
            return True
        return False

    def destroy(self):
        self.quit_signal.emit()

        if self.timer is not None:
            self.timer.cancel()

        self.tray_icon.hide()
        self.app.quit()

    def draw_library(self, clear=False):
        self.set_status("Reading local builds", False)

        if clear:
            self.cm = ConnectionManager(version=version, proxy_type=get_proxy_type())
            self.cm.setup()
            self.cm.error.connect(self.connection_error)
            self.manager = self.cm.manager

            if self.timer is not None:
                self.timer.cancel()

            self.scraper.quit()
            self.DownloadsStableListWidget.clear_()
            self.DownloadsDailyListWidget.clear_()
            self.DownloadsExperimentalListWidget.clear_()
            self.started = True

        self.favorite = None

        self.LibraryStableListWidget.clear_()
        self.LibraryDailyListWidget.clear_()
        self.LibraryExperimentalListWidget.clear_()
        self.UserCustomListWidget.clear_()
        self.PreferencesListWidget.clear_()

        self.library_drawer = DrawLibraryTask()
        self.library_drawer.found.connect(self.draw_to_library)
        self.library_drawer.unrecognized.connect(self.draw_unrecognized)
        if "-offline" not in self.argv:
            self.library_drawer.finished.connect(self.draw_downloads)

        self.task_queue.append(self.library_drawer)

    def reload_custom_builds(self):
        self.UserCustomListWidget.clear_()

        self.library_drawer = DrawLibraryTask(["custom"])
        self.library_drawer.found.connect(self.draw_to_library)
        self.library_drawer.unrecognized.connect(self.draw_unrecognized)
        self.task_queue.append(self.library_drawer)

    def draw_downloads(self):
        self.set_status("Checking for new builds", False)

        for page in self.DownloadsToolBox.pages:
            page.set_info_label_text("Checking for new builds")

        self.cashed_builds.clear()
        self.new_downloads = False
        self.app_state = AppState.CHECKINGBUILDS
        self.scraper = Scraper(self, self.cm)
        self.scraper.links.connect(self.draw_to_downloads)
        self.scraper.new_bl_version.connect(self.set_version)
        self.scraper.error.connect(self.connection_error)
        self.scraper.finished.connect(self.scraper_finished)
        self.scraper.start()

    def connection_error(self):
        print("connection_error")
        set_locale()
        utcnow = strftime(("%H:%M"), localtime())
        self.set_status("Error: connection failed at " + utcnow)
        self.app_state = AppState.IDLE

        # if get_check_for_new_builds_automatically() is True:
        #     self.timer = threading.Timer(
        #         get_new_builds_check_frequency(), self.draw_downloads)
        #     self.timer.start()

    def scraper_finished(self):
        if self.new_downloads and not self.started:
            self.show_message("New builds of Blender are available!", message_type=MessageType.NEWBUILDS)

        for list_widget in self.DownloadsToolBox.list_widgets:
            for widget in list_widget.widgets.copy():
                if widget.build_info not in self.cashed_builds:
                    widget.destroy()

        set_locale()
        utcnow = strftime(("%H:%M"), localtime())
        self.app_state = AppState.IDLE

        for page in self.DownloadsToolBox.pages:
            page.set_info_label_text("No new builds available")

        # if get_check_for_new_builds_automatically() is True:
        #     self.timer = threading.Timer(
        #         get_new_builds_check_frequency(), self.draw_downloads)
        #     self.timer.start()
        #     self.started = False

        self.set_status("Last check at " + utcnow, True)

    def draw_from_cashed(self, build_info):
        if self.app_state == AppState.IDLE:
            for cashed_build in self.cashed_builds:
                if build_info == cashed_build:
                    self.draw_to_downloads(cashed_build, False)
                    return

    def draw_to_downloads(self, build_info, show_new=True):
        if self.started:
            show_new = False

        if build_info not in self.cashed_builds:
            self.cashed_builds.append(build_info)

        branch = build_info.branch

        if branch in ("stable", "lts"):
            downloads_list_widget = self.DownloadsStableListWidget
            library_list_widget = self.LibraryStableListWidget
        elif branch == "daily":
            downloads_list_widget = self.DownloadsDailyListWidget
            library_list_widget = self.LibraryDailyListWidget
        else:
            downloads_list_widget = self.DownloadsExperimentalListWidget
            library_list_widget = self.LibraryExperimentalListWidget

        is_installed = library_list_widget.contains_build_info(build_info)

        if is_installed:
            show_new = True

        if not downloads_list_widget.contains_build_info(build_info):
            item = BaseListWidgetItem(build_info.commit_time)
            widget = DownloadWidget(self, downloads_list_widget, item, build_info, show_new, is_installed)
            downloads_list_widget.add_item(item, widget)
            if is_installed:
                self.new_downloads = True

    def draw_to_library(self, path, show_new=False):
        branch = Path(path).parent.name

        if branch in ("stable", "lts"):
            list_widget = self.LibraryStableListWidget
        elif branch == "daily":
            list_widget = self.LibraryDailyListWidget
        elif branch == "experimental":
            list_widget = self.LibraryExperimentalListWidget
        elif branch == "custom":
            list_widget = self.UserCustomListWidget
        else:
            return

        item = BaseListWidgetItem()
        widget = LibraryWidget(self, item, path, list_widget, show_new)
        list_widget.insert_item(item, widget)

    def draw_unrecognized(self, path):
        branch = Path(path).parent.name

        if branch in ("stable", "lts"):
            list_widget = self.LibraryStableListWidget
        elif branch == "daily":
            list_widget = self.LibraryDailyListWidget
        elif branch == "experimental":
            list_widget = self.LibraryExperimentalListWidget
        elif branch == "custom":
            list_widget = self.UserCustomListWidget
        else:
            return

        item = BaseListWidgetItem()
        widget = UnrecoBuildWidget(self, path, list_widget, item)

        list_widget.insert_item(item, widget)

    def draw_preferences_factory(self):
        item = BaseListWidgetItem()
        self.PreferencesListWidget.add_item(item, PreferenceFactoryWidget(self, self.PreferencesListWidget))

    def set_status(self, status=None, is_force_check_on=None):
        if status is not None:
            self.status = status

        if is_force_check_on is not None:
            self.is_force_check_on = is_force_check_on

        self.ForceCheckNewBuilds.setEnabled(self.is_force_check_on)
        self.statusbarLabel.setText(self.status)

    def set_version(self, latest_tag):
        if "dev" in self.version:
            return

        latest_ver = re.sub(r"\D", "", latest_tag)
        current_ver = re.sub(r"\D", "", self.version)

        if int(latest_ver) > int(current_ver):
            if latest_tag not in self.notification_pool:
                self.NewVersionButton.setText(f"Update to version {latest_tag.replace('v', '')}")
                self.NewVersionButton.show()
                self.show_message("New version of Blender Launcher is available!", value=latest_tag)

            self.latest_tag = latest_tag

    def show_settings_window(self):
        self.settings_window = SettingsWindow(parent=self)

    def clear_temp(self, path=None):
        if path is None:
            path = Path(get_library_folder()) / ".temp"
        a = RemovalTask(path)
        self.task_queue.append(a)

    @pyqtSlot()
    def attempt_close(self):
        if get_show_tray_icon():
            self.close()
        else:
            self.quit_()

    def closeEvent(self, event):
        if get_show_tray_icon():
            event.ignore()
            self.hide()
            self.close_signal.emit()
        else:
            self.destroy()

    def new_connection(self):
        self.socket = self.server.nextPendingConnection()
        assert self.socket is not None
        self.socket.readyRead.connect(self.read_socket_data)
        self._show()

    def read_socket_data(self):
        assert self.socket is not None
        data = self.socket.readAll()

        if str(data, encoding="ascii") != self.version:
            self.dlg = DialogWindow(
                parent=self,
                title="Warning",
                text="An attempt to launch a different version<br>\
                      of Blender Launcher was detected!<br>\
                      Please, terminate currently running<br>\
                      version to proceed this action!",
                accept_text="OK",
                cancel_text=None,
                icon=DialogIcon.WARNING,
            )

    def open_docs(self):
        webbrowser.open("https://Victor-IX.github.io/Blender-Launcher-V2")

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasFormat("text/plain"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        print(e.mimeData().text())

    def restart_app(self):
        """Launch 'Blender Launcher.exe' and exit"""
        cwd = get_cwd()

        if self.platform == "Windows":
            exe = (cwd / "Blender Launcher.exe").as_posix()
            _popen([exe, "-instanced"])
        elif self.platform == "Linux":
            exe = (cwd / "Blender Launcher").as_posix()
            os.chmod(exe, 0o744)
            _popen('nohup "' + exe + '" -instanced')

        self.destroy()
