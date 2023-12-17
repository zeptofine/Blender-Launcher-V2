from __future__ import annotations

import json
import os
from typing import TypedDict

import distro
from modules._platform import _popen, get_cwd, get_platform
from modules.actions import ActionQueue
from threads.downloader import DownloadAction
from threads.extractor import ExtractAction
from ui.update_window_ui import UpdateWindowUI
from windows.base_window import BaseWindow

release_link = "https://github.com/Victor-IX/Blender-Launcher-V2/releases/download/{0}/Blender_Launcher_{0}_{1}_x64.zip"
api_link = "https://api.github.com/repos/Victor-IX/Blender-Launcher-V2/releases/tags/{}"


# this only shows relevant sections of the response
class GitHubAsset(TypedDict):
    url: str
    name: str
    browser_download_url: str


class GitHubRelease(TypedDict):
    assets: list[GitHubAsset]


class BlenderLauncherUpdater(BaseWindow, UpdateWindowUI):
    def __init__(self, app, version, release_tag):
        super().__init__(app=app, version=version)
        self.setupUi(self)

        self._headers = {
            "X-GitHub-Api-Version": "2022-11-28",
        }

        self.release_tag = release_tag
        self.platform = get_platform()
        self.cwd = get_cwd()

        self.queue = ActionQueue(parent=self, worker_count=1)
        self.queue.start()

        self.show()
        self.download()

    def get_link(self, response: GitHubRelease | None = None) -> str:
        assert self.manager is not None
        if response is None:
            api_req = api_link.format(self.release_tag)
            d = self.manager.request("GET", api_req, headers=self._headers)
            assert d.data is not None
            response = json.loads(d.data)
        assert response is not None

        assets = response["assets"]
        asset_table = {}  # {"<Distro>": asset}
        for asset in assets:
            if self.release_tag in asset["name"]:  # can never be so sure
                release_idx = asset["name"].find(self.release_tag) + len(self.release_tag) + 1
                asset_table[asset["name"][release_idx:-8]] = asset

        release = asset_table.get("Ubuntu", asset_table.get("Linux"))
        if release is None:
            return release_link.format(self.release_tag, self.platform)

        for key in (
            distro.id().title(),
            distro.like().title(),
            distro.id(),
            distro.like(),
        ):
            if key in asset_table:
                release = asset_table[key]
                break

        return release["browser_download_url"]

    def download(self):
        # TODO
        # This function should not use proxy for downloading new builds!
        link = self.get_link() if self.platform == "Linux" else release_link.format(self.release_tag, self.platform)

        assert self.manager is not None
        a = DownloadAction(self.manager, link)
        a.progress.connect(self.ProgressBar.set_progress)
        a.finished.connect(self.extract)
        self.queue.append(a)

    def extract(self, source):
        a = ExtractAction(source, self.cwd)
        a.progress.connect(self.ProgressBar.set_progress)
        a.finished.connect(self.finish)
        self.queue.append(a)

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
