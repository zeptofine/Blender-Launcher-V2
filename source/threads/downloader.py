from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from modules._copyfileobj import copyfileobj
from modules.action import Action
from modules.connection_manager import REQUEST_MANAGER
from modules.settings import get_library_folder
from PyQt5.QtCore import pyqtSignal


def download(
    manager: REQUEST_MANAGER,
    link,
    progress_callback: Callable[[int, int], None],
) -> Path:
    progress_callback(0, 0)
    temp_folder = Path(get_library_folder()) / ".temp"

    temp_folder.mkdir(exist_ok=True)

    dist = temp_folder / Path(link).name

    with manager.request("GET", link, preload_content=False) as r:
        size = int(r.headers["Content-Length"])
        with dist.open("wb") as f:
            copyfileobj(r, f, lambda x: progress_callback(x, size))

    r.release_conn()
    r.close()

    return dist


@dataclass(frozen=True)
class DownloadAction(Action):
    manager: REQUEST_MANAGER
    link: str
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(Path)

    def run(self):
        dst = download(
            manager=self.manager,
            link=self.link,
            progress_callback=self.progress.emit,
        )
        self.finished.emit(dst)
