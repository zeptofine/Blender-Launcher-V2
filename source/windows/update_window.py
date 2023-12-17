import os

from modules._platform import _popen, get_cwd, get_platform
from modules.actions import ActionQueue
from threads.downloader import DownloadAction
from threads.extractor import ExtractAction, Extractor
from ui.update_window_ui import UpdateWindowUI
from windows.base_window import BaseWindow

link = "https://github.com/Victor-IX/Blender-Launcher/releases/download/{0}/Blender_Launcher_{0}_{1}_x64.zip"


class BlenderLauncherUpdater(BaseWindow, UpdateWindowUI):
    def __init__(self, app, version, release_tag):
        super().__init__(app=app, version=version)
        self.setupUi(self)

        self.release_tag = release_tag
        self.platform = get_platform()
        self.cwd = get_cwd()

        self.queue = ActionQueue(parent=self, worker_count=1)
        self.queue.start()

        self.show()
        self.download()

    def download(self):
        # TODO
        # This function should not use proxy for downloading new builds!
        self.link = link.format(self.release_tag, self.platform)
        assert self.manager is not None
        a = DownloadAction(self.manager, self.link)
        a.progress.connect(self.ProgressBar.set_progress)
        a.finished.connect(self.extract)
        self.queue.put(a)

    def extract(self, source):
        a = ExtractAction(source, self.cwd)
        a.progress.connect(self.ProgressBar.set_progress)
        a.finished.connect(self.finish)
        self.queue.put(a)

    def finish(self, dist):
        # Launch 'Blender Launcher.exe' and exit
        launcher = str(dist)
        if self.platform == "Windows":
            _popen([launcher])
        elif self.platform == "Linux":
            os.chmod(dist, 0o744)
            _popen('nohup "' + launcher + '"')

        self.app.quit()

    def closeEvent(self, event):
        self.queue.fullstop()
        event.ignore()
        self.showMinimized()
