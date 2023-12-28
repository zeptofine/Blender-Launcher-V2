from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from modules._platform import _check_output, get_platform, set_locale
from modules.action import Action
from PyQt5.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class BuildInfo:
    # Class variables
    file_version = "1.3"
    # https://www.blender.org/download/lts/
    lts_tags = ("2.83", "2.93", "3.3", "3.7")

    # Build variables
    link: str
    subversion: str
    build_hash: str
    commit_time: str
    branch: str
    custom_name: str = ""
    is_favorite: bool = False
    custom_executable: str | None = None

    def __post_init__(self):
        if any(w in self.subversion.lower() for w in ["release", "rc"]):
            self.subversion = re.sub("[a-zA-Z ]+", " Candidate ", self.subversion).rstrip()

        if self.branch == "stable" and self.subversion.startswith(self.lts_tags):
            self.branch = "lts"

    def __eq__(self, other: BuildInfo):
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
            blinfo.get("custom_executable", ""),
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
                    "custom_executable": self.custom_executable,
                }
            ],
        }

    def write_to(self, path: Path):
        data = self.to_dict()
        blinfo = path / ".blinfo"
        with blinfo.open("w", encoding="utf-8") as file:
            json.dump(data, file)
        return data


def get_blender_ver_info(exe: Path) -> tuple[str, str, str, str]:
    version = _check_output([exe.as_posix(), "-v"]).decode("UTF-8")

    commit_time = ""
    build_hash = ""
    subversion = ""
    custom_name = ""

    ctime = re.search("build commit time: (.*)", version)
    cdate = re.search("build commit date: (.*)", version)

    if ctime is not None and cdate is not None:
        strptime = time.strptime(
            f"{cdate[1].rstrip()} {ctime[1].rstrip()}",
            "%Y-%m-%d %H:%M",
        )
        commit_time = time.strftime("%d-%b-%y-%H:%M", strptime)

    if s := re.search("build hash: (.*)", version):
        build_hash = s[1].rstrip()

    if s := re.search("Blender (.*)", version):

        subversion = s[1].rstrip()
    else:
        s = version.splitlines()[0].strip()
        custom_name, subversion = s.rsplit(" ", 1)

    return (
        commit_time,
        build_hash,
        subversion,
        custom_name,
    )


def read_blender_version(
    path: Path,
    old_build_info: BuildInfo | None = None,
    archive_name=None,
    custom_exe=None,
) -> BuildInfo:
    set_locale()

    if custom_exe is not None:
        exe_path = path / custom_exe
    elif old_build_info is not None and old_build_info.custom_executable:
        exe_path = path / old_build_info.custom_executable
    else:
        blender_exe = {
            "Windows": "blender.exe",
            "Linux": "blender",
            "macOS": "Blender/Blender.app/Contents/MacOS/Blender",
        }.get(get_platform(), "blender")

        exe_path = path / blender_exe

    commit_time, build_hash, subversion, custom_name = get_blender_ver_info(exe_path)

    subfolder = path.parent.name

    name = archive_name or path.name
    branch = subfolder
    if subfolder == "daily":
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

    # Recover user defined favorites builds information
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
        custom_executable=custom_exe
    )


@dataclass(frozen=True)
class WriteBuildAction(Action):
    written = pyqtSignal()
    error = pyqtSignal()

    path: Path
    build_info: BuildInfo

    def run(self):
        try:
            self.build_info.write_to(self.path)
            self.written.emit()
        except Exception:
            self.error.emit()
            raise


def read_build_info(path: Path, archive_name: str | None = None, custom_exe: str | None = None, auto_write=True):
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
                custom_exe,
            )
            new_build_info.write_to(path)
            return new_build_info
        return build_info

    # Generating new build information
    build_info = read_blender_version(
        path,
        archive_name=archive_name,
        custom_exe=custom_exe,
    )
    if auto_write:
        build_info.write_to(path)
    return build_info


@dataclass(frozen=True)
class ReadBuildAction(Action):
    path: Path
    archive_name: str | None = None
    custom_exe: str | None = None
    auto_write: bool = True

    finished = pyqtSignal(BuildInfo)
    failure = pyqtSignal(Exception)

    def run(self):
        try:
            build_info = read_build_info(self.path, self.archive_name, self.custom_exe, self.auto_write)
            self.finished.emit(build_info)
        except Exception as e:
            self.failure.emit(e)
            raise

    def __str__(self):
        return f"Read build at {self.path}"
