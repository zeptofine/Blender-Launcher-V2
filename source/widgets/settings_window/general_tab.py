import os

from modules.settings import (
    get_check_for_new_builds_automatically,
    get_check_for_new_builds_on_startup,
    get_enable_high_dpi_scaling,
    get_launch_minimized_to_tray,
    get_launch_when_system_starts,
    get_library_folder,
    get_make_error_popup,
    get_new_builds_check_frequency,
    get_platform,
    get_show_tray_icon,
    get_use_system_titlebar,
    get_worker_thread_count,
    set_check_for_new_builds_automatically,
    set_check_for_new_builds_on_startup,
    set_enable_high_dpi_scaling,
    set_launch_minimized_to_tray,
    set_launch_when_system_starts,
    set_library_folder,
    set_make_error_popup,
    set_new_builds_check_frequency,
    set_show_tray_icon,
    set_use_system_titlebar,
    set_worker_thread_count,
)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QWidget
from widgets.settings_form_widget import SettingsFormWidget
from windows.dialog_window import DialogWindow
from windows.file_dialog_window import FileDialogWindow


class GeneralTabWidget(SettingsFormWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        # Library Folder
        self.LibraryFolderLineEdit = QLineEdit()
        self.LibraryFolderLineEdit.setText(str(get_library_folder()))
        self.LibraryFolderLineEdit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.LibraryFolderLineEdit.setReadOnly(True)
        self.LibraryFolderLineEdit.setCursorPosition(0)

        self.SetLibraryFolderButton = QPushButton(self.parent.icons.folder, "")
        self.SetLibraryFolderButton.clicked.connect(self.set_library_folder)

        self.LibraryFolderWidget = QWidget()
        self.LibraryFolderLayout = QHBoxLayout(self.LibraryFolderWidget)
        self.LibraryFolderLayout.setContentsMargins(6, 0, 6, 0)
        self.LibraryFolderLayout.setSpacing(0)

        self.LibraryFolderLayout.addWidget(self.LibraryFolderLineEdit)
        self.LibraryFolderLayout.addWidget(self.SetLibraryFolderButton)

        # Launch When System Starts
        self.LaunchWhenSystemStartsCheckBox = QCheckBox()
        self.LaunchWhenSystemStartsCheckBox.setChecked(get_launch_when_system_starts())
        self.LaunchWhenSystemStartsCheckBox.clicked.connect(self.toggle_launch_when_system_starts)

        # Launch Minimized To Tray
        self.LaunchMinimizedToTrayCheckBox = QCheckBox()
        self.LaunchMinimizedToTrayCheckBox.setChecked(get_launch_minimized_to_tray())
        self.LaunchMinimizedToTrayCheckBox.clicked.connect(self.toggle_launch_minimized_to_tray)

        # Show Tray Icon
        self.ShowTrayIconCheckBox = QCheckBox()
        self.ShowTrayIconCheckBox.setChecked(get_show_tray_icon())
        self.ShowTrayIconCheckBox.clicked.connect(self.toggle_show_tray_icon)

        # Use System Title Bar
        self.UseSystemTitleBar = QCheckBox()
        self.UseSystemTitleBar.setChecked(get_use_system_titlebar())
        self.UseSystemTitleBar.clicked.connect(self.toggle_system_titlebar)

        # New Builds Check Settings
        self.CheckForNewBuildsAutomatically = QCheckBox()
        self.CheckForNewBuildsAutomatically.setChecked(False)
        self.CheckForNewBuildsAutomatically.clicked.connect(self.toggle_check_for_new_builds_automatically)
        self.NewBuildsCheckFrequency = QSpinBox()
        self.NewBuildsCheckFrequency.setEnabled(get_check_for_new_builds_automatically())
        self.NewBuildsCheckFrequency.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.NewBuildsCheckFrequency.setToolTip("Time in hours between new builds check")
        self.NewBuildsCheckFrequency.setMaximum(24*7*4) # 4 weeks?
        self.NewBuildsCheckFrequency.setMinimum(12)
        self.NewBuildsCheckFrequency.setSuffix("h")
        self.NewBuildsCheckFrequency.setValue(get_new_builds_check_frequency())
        self.NewBuildsCheckFrequency.editingFinished.connect(self.new_builds_check_frequency_changed)
        self.CheckForNewBuildsOnStartup = QCheckBox()
        self.CheckForNewBuildsOnStartup.setChecked(get_check_for_new_builds_on_startup())
        self.CheckForNewBuildsOnStartup.clicked.connect(self.toggle_check_on_startup)


        # High Dpi Scaling
        self.EnableHighDpiScalingCheckBox = QCheckBox()
        self.EnableHighDpiScalingCheckBox.clicked.connect(self.toggle_enable_high_dpi_scaling)
        self.EnableHighDpiScalingCheckBox.setChecked(get_enable_high_dpi_scaling())

        # Error popups
        self.EnableErrorPopupsCheckBox = QCheckBox(self)
        self.EnableErrorPopupsCheckBox.clicked.connect(self.toggle_enable_error_popups)
        self.EnableErrorPopupsCheckBox.setChecked(get_make_error_popup())

        # Worker thread count

        self.WorkerThreadCount = QSpinBox()

        self.WorkerThreadCount.setToolTip(
            "Determines how many IO operations can be done at once, ex. Downloading, deleting, and extracting files"
        )
        self.WorkerThreadCount.editingFinished.connect(self.set_worker_thread_count)
        self.WorkerThreadCount.setMinimum(1)
        self.WorkerThreadCount.setValue(get_worker_thread_count())

        # Warn if thread count exceeds cpu count
        cpu_count = os.cpu_count()
        if cpu_count is not None:

            def warn_values_above_cpu(v: int):
                if v > cpu_count:
                    self.WorkerThreadCount.setSuffix(f" (warning: value above {cpu_count} (cpu count) !!)")
                else:
                    self.WorkerThreadCount.setSuffix(None)

            self.WorkerThreadCount.valueChanged.connect(warn_values_above_cpu)

        # Layout
        self._addRow("Library Folder", self.LibraryFolderWidget, new_line=True)

        if get_platform() == "Windows":
            self._addRow("Launch When System Starts", self.LaunchWhenSystemStartsCheckBox)

        self._addRow("Show Tray Icon", self.ShowTrayIconCheckBox)
        self.LaunchMinimizedToTrayRow = self._addRow("Launch Minimized To Tray", self.LaunchMinimizedToTrayCheckBox)
        self.LaunchMinimizedToTrayRow.setEnabled(get_show_tray_icon())
        self._addRow("Use System Title Bar", self.UseSystemTitleBar)

        sub_layout = QHBoxLayout()
        sub_layout.addWidget(self.CheckForNewBuildsAutomatically)
        sub_layout.addWidget(self.NewBuildsCheckFrequency)
        self._addRow("Check For New Builds Automatically", sub_layout)
        self._addRow("Check For New Builds on Startup", self.CheckForNewBuildsOnStartup)
        self._addRow("Enable High DPI Scaling", self.EnableHighDpiScalingCheckBox)
        self._addRow("Enable Error Popups", self.EnableErrorPopupsCheckBox)
        self._addRow("Worker Thread Count", self.WorkerThreadCount)

    def set_library_folder(self):
        library_folder = str(get_library_folder())
        new_library_folder = FileDialogWindow().get_directory(self, "Select Library Folder", library_folder)

        if new_library_folder and (library_folder != new_library_folder):
            if set_library_folder(new_library_folder) is True:
                self.LibraryFolderLineEdit.setText(new_library_folder)
                self.parent.draw_library(clear=True)
            else:
                self.dlg = DialogWindow(
                    parent=self.parent,
                    title="Warning",
                    text="Selected folder doesn't have write permissions!",
                    accept_text="Retry",
                    cancel_text=None,
                )
                self.dlg.accepted.connect(self.set_library_folder)

    def toggle_launch_when_system_starts(self, is_checked):
        set_launch_when_system_starts(is_checked)

    def toggle_launch_minimized_to_tray(self, is_checked):
        set_launch_minimized_to_tray(is_checked)

    def toggle_show_tray_icon(self, is_checked):
        set_show_tray_icon(is_checked)
        self.LaunchMinimizedToTrayRow.setEnabled(is_checked)
        self.parent.tray_icon.setVisible(is_checked)

    def toggle_system_titlebar(self, is_checked):
        set_use_system_titlebar(is_checked)
        self.parent.update_system_titlebar(is_checked)

    def toggle_check_for_new_builds_automatically(self, is_checked):
        set_check_for_new_builds_automatically(is_checked)
        self.NewBuildsCheckFrequency.setEnabled(is_checked)

    def new_builds_check_frequency_changed(self):
        set_new_builds_check_frequency(self.NewBuildsCheckFrequency.value() * 60)

    def toggle_check_on_startup(self, is_checked):
        set_check_for_new_builds_on_startup(is_checked)
        self.CheckForNewBuildsOnStartup.setChecked(is_checked)

    def toggle_enable_high_dpi_scaling(self, is_checked):
        set_enable_high_dpi_scaling(is_checked)

    def toggle_enable_error_popups(self, is_checked):
        set_make_error_popup(is_checked)

    def set_worker_thread_count(self):
        set_worker_thread_count(self.WorkerThreadCount.value())
