from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from modules._platform import _check_output, get_platform, set_locale
from PyQt5.QtCore import QThread, pyqtSignal

from .action import Action


class BuildInfo:
    file_version = "1.2"
    # https://www.blender.org/download/lts/
    lts_tags = ("2.83", "2.93", "3.3", "3.7")

    def __init__(self, link, subversion, build_hash, commit_time, branch, custom_name="", is_favorite=False):
        self.link = link

        if any(w in subversion.lower() for w in ["release", "rc"]):
            subversion = re.sub("[a-zA-Z ]+", " Candidate ", subversion).rstrip()

        self.subversion = subversion
        self.build_hash = build_hash
        self.commit_time = commit_time

        if branch == "stable" and subversion.startswith(self.lts_tags):
            branch = "lts"

        self.branch = branch
        self.custom_name = custom_name
        self.is_favorite = is_favorite

        self.platform = get_platform()

    def __eq__(self, other):
        if (self is None) or (other is None):
            return False
        if (self.build_hash is not None) and (other.build_hash is not None):
            return self.build_hash == other.build_hash
        return self.subversion == other.subversion

    @classmethod
    def from_dict(cls, path: Path, blinfo: dict):
        return cls(
            path.as_posix(),
            blinfo["subversion"],
            blinfo["build_hash"],
            blinfo["commit_time"],
            blinfo["branch"],
            blinfo["custom_name"],
            blinfo["is_favorite"],
        )

    def to_dict(self):
        return {
            "file_version": self.__class__.file_version,
            "blinfo": [
                {
                    "branch": self.branch,
                    "subversion": self.subversion,
                    "build_hash": self.build_hash,
                    "commit_time": self.commit_time,
                    "custom_name": self.custom_name,
                    "is_favorite": self.is_favorite,
                }
            ],
        }


def write_build_info(build_info: BuildInfo, dist: Path):
    data = build_info.to_dict()
    blinfo = dist / ".blinfo"
    with blinfo.open("w", encoding="utf-8") as file:
        json.dump(data, file)
    return data


def read_blender_version(path: Path, old_build_info: BuildInfo | None = None, archive_name=None):
    set_locale()

    platform = get_platform()
    if platform == "Windows":
        blender_exe = "blender.exe"
    elif platform == "Linux":
        blender_exe = "blender"
    elif platform == "macOS":
        blender_exe = "Blender/Blender.app/Contents/MacOS/Blender"

    exe_path = path / blender_exe
    version = _check_output([exe_path.as_posix(), "-v"])
    version = version.decode("UTF-8")

    ctime = re.search("build commit time: " + "(.*)", version)[1].rstrip()
    cdate = re.search("build commit date: " + "(.*)", version)[1].rstrip()
    strptime = time.strptime(cdate + " " + ctime, "%Y-%m-%d %H:%M")
    commit_time = time.strftime("%d-%b-%y-%H:%M", strptime)
    build_hash = re.search("build hash: " + "(.*)", version)[1].rstrip()
    subversion = re.search("Blender " + "(.*)", version)[1].rstrip()

    subfolder = path.parent.name

    name = archive_name or path.name

    if subfolder == "daily":
        branch = "daily"

        # If branch from console is empty, it is probably stable release
        if len(subversion.split(" ")) == 1:
            subversion += " Stable"
    elif subfolder == "custom":
        branch = name
    elif subfolder == "experimental":
        # Sensitive data! Requires proper folder naming!
        match = re.search(r"\+(.+?)\.", name)

        # Fix for naming conventions changes after 1.12.0 release
        if match is None:
            if old_build_info is not None:
                branch = old_build_info.branch
        else:
            branch = match.group(1)
    elif subfolder == "stable":
        branch = "stable"

    # Recover user defined favorites builds information
    custom_name = ""
    is_favorite = False
    if old_build_info is not None:
        custom_name = old_build_info.custom_name
        is_favorite = old_build_info.is_favorite

    return BuildInfo(
        path.as_posix(),
        subversion,
        build_hash,
        commit_time,
        branch,
        custom_name,
        is_favorite,
    )


class BuildInfoWriter(QThread):
    written = pyqtSignal()
    error = pyqtSignal()

    def __init__(self, path, build_info):
        QThread.__init__(self)
        self.path = Path(path)
        self.build_info: BuildInfo = build_info

    def run(self):
        try:
            write_build_info(self.build_info, self.path)
            self.written.emit()
        except Exception:
            self.error.emit()
            raise


def read_build_info(path: Path, archive_name: str | None = None):
    blinfo = path / ".blinfo"

    # Check if build information is already present
    if blinfo.is_file():
        with blinfo.open(encoding="utf-8") as file:
            data = json.load(file)

        build_info = BuildInfo.from_dict(path, data["blinfo"][0])

        # Check if file version changed
        if ("file_version" not in data) or (data["file_version"] != BuildInfo.file_version):
            new_build_info = read_blender_version(
                path,
                build_info,
                archive_name,
            )
            write_build_info(new_build_info, path)
            return new_build_info
        return build_info

    # Generating new build information
    build_info = read_blender_version(path, archive_name=archive_name)
    write_build_info(build_info, path)
    return build_info


@dataclass(frozen=True)
class ReadBuildAction(Action):
    path: Path
    build_info: str | None = None
    archive_name: str | None = None

    finished = pyqtSignal(BuildInfo)
    failure = pyqtSignal(Exception)

    def run(self):
        try:
            build_info = read_build_info(self.path, self.archive_name)
            self.finished.emit(build_info)
        except Exception as e:
            self.failure.emit(e)
            raise
