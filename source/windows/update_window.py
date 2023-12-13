from __future__ import annotations

import json
import os
from typing import TypedDict

import distro
from modules._platform import _popen, get_cwd, get_platform
from PyQt5.QtWidgets import QMainWindow
from threads.downloader import Downloader
from threads.extractor import Extractor
from ui.update_window_ui import UpdateWindowUI
from windows.base_window import BaseWindow

release_link = "https://github.com/Victor-IX/Blender-Launcher/releases/download/{0}/Blender_Launcher_{0}_{1}_x64.zip"
api_link = "https://api.github.com/repos/Victor-IX/Blender-Launcher-V2/releases/tags/{}"


# this only shows relevant sections of the response
class GitHubAsset(TypedDict):
    url: str
    name: str
    browser_download_url: str


class GitHubRelease(TypedDict):
    assets: list[GitHubAsset]


class BlenderLauncherUpdater(QMainWindow, BaseWindow, UpdateWindowUI):
    def __init__(self, app, version, release_tag):
        super().__init__(app=app, version=version)
        self.setupUi(self)

        self._headers = {
            "X-GitHub-Api-Version": "2022-11-28",
        }

        self.release_tag = release_tag
        self.platform = get_platform()
        self.cwd = get_cwd()

        self.show()
        self.download()

    def get_link(self, response: GitHubRelease | None = None) -> str:
        assert self.manager is not None
        if response is None:
            # api_req = api_link.format(self.release_tag)
            # d = self.manager.request("GET", api_req, headers=self._headers)
            # assert d.data is not None
            # response: GitHubRelease = json.loads(d.data)
            with open("update_test_responses.json") as f:
                response = json.loads(f.read())

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

        from pprint import pprint

        pprint(release)
        exit()

        return release["browser_download_url"]

    def download(self):
        # TODO
        # This function should not use proxy for downloading new builds!
        link = self.get_link() if self.platform == "Linux" else release_link.format(self.release_tag, self.platform)

        self.downloader = Downloader(self.manager, link)
        self.downloader.progress_changed.connect(self.ProgressBar.set_progress)
        self.downloader.finished.connect(self.extract)
        self.downloader.start()

    def extract(self, source):
        self.extractor = Extractor(self.manager, source, self.cwd)
        self.extractor.progress_changed.connect(self.ProgressBar.set_progress)
        self.extractor.finished.connect(self.finish)
        self.extractor.start()

    def finish(self, dist):
        # Launch 'Blender Launcher.exe' and exit
        dist = str(dist)
        if self.platform == "Windows":
            _popen([dist])
        elif self.platform == "Linux":
            os.chmod(dist, 0o744)
            _popen('nohup "' + dist + '"')

        self.app.quit()

    def closeEvent(self, event):
        event.ignore()
        self.showMinimized()
