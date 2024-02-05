from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from bs4 import BeautifulSoup, SoupStrainer
from modules._platform import get_platform, set_locale
from modules.build_info import BuildInfo, parse_blender_ver
from modules.settings import get_minimum_blender_stable_version
from PyQt5.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from modules.connection_manager import ConnectionManager


class Scraper(QThread):
    links = pyqtSignal(BuildInfo)
    new_bl_version = pyqtSignal(str)
    error = pyqtSignal()

    def __init__(self, parent, man):
        QThread.__init__(self)
        self.parent = parent
        self.manager: ConnectionManager = man
        self.platform = get_platform()
        self.json_platform = {
            "Windows": "windows",
            "Linux": "linux",
            "macOS": "darwin",
        }.get(self.platform, self.platform)

        if self.platform == "Windows":
            regex_filter = r"blender-.+win.+64.+zip$"
        elif self.platform == "macOS":
            regex_filter = r"blender-.+(macOS|darwin).+dmg$"
        else:
            regex_filter = r"blender-.+lin.+64.+tar+(?!.*sha256).*"

        self.b3d_link = re.compile(regex_filter, re.IGNORECASE)
        self.hash = re.compile(r"\w{12}")
        self.subversion = re.compile(r"-\d\.[a-zA-Z0-9.]+-")

    def run(self):
        self.get_download_links()
        latest_tag = self.get_latest_tag()
        if latest_tag is not None:
            self.new_bl_version.emit(latest_tag)
        self.manager.manager.clear()

    def get_latest_tag(self) -> str | None:
        r = self.manager.request(
            "GET",
            "https://github.com/Victor-IX/Blender-Launcher-V2/releases/latest",
        )

        if r is None:
            return None

        url = r.geturl()
        tag = url.rsplit("/", 1)[-1]

        r.release_conn()
        r.close()

        return tag

    def get_download_links(self):
        # Stable Builds
        self.scrap_stable_releases()

        # Daily, Experimental build
        self.gather_automated_builds()

    def gather_automated_builds(self):
        base_fmt = "https://builder.blender.org/download/{}/?format=json&v=1"
        for branch_type in ("daily", "experimental", "patch"):
            url = base_fmt.format(branch_type)
            r = self.manager.request("GET", url)

            if r is None:
                continue

            data = json.loads(r.data)
            for build in data:
                if build["platform"] == self.json_platform and self.b3d_link.match(build["file_name"]):
                    new_build = self.new_build_from_dict(build, branch_type)
                    self.links.emit(new_build)

    def new_build_from_dict(self, build, branch_type):
        self.strptime = datetime.fromtimestamp(build["file_mtime"], tz=timezone.utc)

        subversion = parse_blender_ver(build["version"])
        build_var = ""
        if build["patch"] is not None and branch_type != "daily":
            build_var = build["patch"]
        if build["release_cycle"] is not None and branch_type == "daily":
            build_var = build["release_cycle"]
        if build["branch"] and branch_type == "experimental":
            build_var = build["branch"]

        if build_var:
            subversion = subversion.replace(prerelease=build_var)

        return BuildInfo(
            build["url"],
            str(subversion),
            build["hash"],
            self.strptime,
            branch_type,
        )

    def scrap_download_links(self, url, branch_type, _limit=None, stable=False):
        r = self.manager.request("GET", url)

        if r is None:
            return

        content = r.data

        soup_stainer = SoupStrainer("a", href=True)
        soup = BeautifulSoup(content, "lxml", parse_only=soup_stainer)

        for tag in soup.find_all(limit=_limit, href=self.b3d_link):
            build_info = self.new_blender_build(tag, url, branch_type)

            if build_info is not None:
                self.links.emit(build_info)

        r.release_conn()
        r.close()

    def new_blender_build(self, tag, url, branch_type):
        link = urljoin(url, tag["href"]).rstrip("/")
        r = self.manager.request("HEAD", link)

        if r is None:
            return None

        if r.status != 200:
            return None

        info = r.headers
        build_hash: str | None = None
        stem = Path(link).stem
        match = re.findall(self.hash, stem)

        if match:
            build_hash = match[-1].replace("-", "")

        subversion = parse_blender_ver(stem, search=True)
        branch = branch_type
        if branch_type != "stable":
            build_var = ""
            tag = tag.find_next("span", class_="build-var")

            # For some reason tag can be None on macOS
            if tag is not None:
                build_var = tag.get_text()

            if self.platform == "macOS":
                if "arm64" in link:
                    build_var = "{} │ {}".format(build_var, "Arm")
                elif "x86_64" in link:
                    build_var = "{} │ {}".format(build_var, "Intel")

            if branch_type == "experimental":
                branch = build_var
            elif branch_type == "daily":
                branch = "daily"
                subversion = subversion.replace(prerelease=build_var)

        set_locale()
        self.strptime = datetime.strptime(info["last-modified"], "%a, %d %b %Y %H:%M:%S %Z").astimezone()
        commit_time = self.strptime

        r.release_conn()
        r.close()
        return BuildInfo(link, str(subversion), build_hash, commit_time, branch)

    def scrap_stable_releases(self):
        url = "https://download.blender.org/release/"
        r = self.manager.request("GET", url)

        if r is None:
            return

        content = r.data
        soup = BeautifulSoup(content, "lxml")

        b3d_link = re.compile(r"Blender\d+\.\d+")
        subversion = re.compile(r"\d+\.\d+")

        releases = soup.find_all(href=b3d_link)
        if not any(releases):
            logging.info("Failed to gather stable releases")

        minimum_version = get_minimum_blender_stable_version()

        for release in releases:
            href = release["href"]
            match = re.search(subversion, href)
            if match is None:
                continue

            ver = parse_blender_ver(match.group(0))
            if ver >= minimum_version:
                self.scrap_download_links(urljoin(url, href), "stable", stable=True)

        r.release_conn()
        r.close()
