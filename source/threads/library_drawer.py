from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from modules._platform import get_platform
from modules.settings import get_library_folder
from modules.task import Task
from PyQt5.QtCore import pyqtSignal

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class DrawLibraryTask(Task):
    folders: Iterable[str | Path] = ("stable", "daily", "experimental", "custom")
    found = pyqtSignal(Path)
    unrecognized = pyqtSignal(Path)
    finished = pyqtSignal()

    def run(self):
        library_folder = Path(get_library_folder())
        platform = get_platform()

        blender_exe = {
            "Windows": "blender.exe",
            "Linux": "blender",
            "macOS": "Blender/Blender.app/Contents/MacOS/Blender",
        }.get(platform, "blender")

        for folder in self.folders:
            path = library_folder / folder

            if path.is_dir():
                for build in path.iterdir():
                    if build.is_dir():
                        if (folder / build / ".blinfo").is_file() or (path / build / blender_exe).is_file():
                            self.found.emit(folder / build)
                        else:
                            self.unrecognized.emit(folder / build)
        self.finished.emit()

    def __str__(self):
        return f"Draw libraries {self.folders}"
