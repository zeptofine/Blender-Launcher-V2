from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from modules._platform import get_platform
from modules.action import Action
from modules.settings import get_library_folder
from PyQt5.QtCore import pyqtSignal

if TYPE_CHECKING:
    from collections.abc import Iterable


def get_builds(folders: Iterable[str | Path]):
    library_folder = Path(get_library_folder())
    platform = get_platform()

    if platform == "Windows":
        blender_exe = "blender.exe"
    elif platform == "Linux":
        blender_exe = "blender"
    elif platform == "macOS":
        blender_exe = "Blender/Blender.app/Contents/MacOS/Blender"

    for folder in folders:
        path = library_folder / folder

        if path.is_dir():
            for build in path.iterdir():
                if (path / build / blender_exe).is_file():
                    yield folder / build


@dataclass(frozen=True)
class DrawLibraryAction(Action):
    folders: Iterable[str | Path] = ("stable", "daily", "experimental", "custom")
    found = pyqtSignal(Path)
    finished = pyqtSignal()

    def run(self):
        for build in get_builds(self.folders):
            self.found.emit(build)
        self.finished.emit()
