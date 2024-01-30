from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache
from typing import TYPE_CHECKING

from modules._platform import _check_output, get_platform, set_locale
from modules.task import Task
from PyQt5.QtCore import pyqtSignal
from semver import Version

if TYPE_CHECKING:
    from pathlib import Path

# TODO: Combine some of these
matchers = tuple(
    map(
        re.compile,
        (
            r"(?P<ma>\d+)\.(?P<mi>\d+)\.(?P<pa>\d+) (?P<pre>.*)",  # <major>.<minor>.<patch> <Prerelease>
            r"(?P<ma>\d+)\.(?P<mi>\d+) \(sub (?P<pa>\d+)\)",  # <major>.<minor> (sub <patch>)
            r"(?P<ma>\d+)\.(?P<mi>\d+)(?P<pre>\D[^\.\s]*)",  # <major>.<minor><patch>
            r"(?P<ma>\d+)\.(?P<mi>\d+)",  # <major>.<minor>
        ),
    )
)


def print_output(func):
    def p_o(*args, **kwargs):
        v = func(*args, **kwargs)
        print(f"{func}({', '.join(args)}, **{kwargs}) -> {v!r}")
        return v

    return p_o


@cache
def parse_blender_ver(s: str) -> Version:
    """
    Converts Blender's different styles of versioning to a semver Version.
    Assumes s is either a semantic version or a blender style version. Otherwise things might get messy
    Versions ending with 'a' and 'b' will have a patch of 1 and 2.


    Arguments:
        s -- a blender version.

    Returns:
        Version
    """
    try:
        return Version.parse(s)
    except ValueError as e:
        major = 0
        minor = 0
        patch = 0
        prerelease = None

        try:
            g = next(m for matcher in matchers if (m := matcher.match(s)) is not None)
        except StopIteration:
            """No matcher gave any valid version"""
            raise ValueError("No valid version found") from e

        major = int(g.group("ma"))
        minor = int(g.group("mi"))
        if "pa" in g.groupdict():
            patch = int(g.group("pa"))
        if "pre" in g.groupdict():
            prerelease = g.group("pre").casefold()

        return Version(major=major, minor=minor, patch=patch, prerelease=prerelease)


@dataclass
class BuildInfo:
    # Class variables
    file_version = "1.3"
    # https://www.blender.org/download/lts/
    lts_tags = ("2.83", "2.93", "3.3", "3.6", "4.3", "4.6")

    # Build variables
    link: str
    subversion: str
    build_hash: str | None
    commit_time: datetime
    branch: str
    custom_name: str = ""
    is_favorite: bool = False
    custom_executable: str | None = None

    def __post_init__(self):
        print(f"({self.branch})[{self.subversion}] -> {self.semversion} or {self.full_semversion} from {self.link}")
        if self.branch == "stable" and self.subversion.startswith(self.lts_tags):
            self.branch = "lts"

    def __eq__(self, other: BuildInfo):
        if (self is None) or (other is None):
            return False
        if (self.build_hash is not None) and (other.build_hash is not None):
            return self.build_hash == other.build_hash
        return self.subversion == other.subversion

    @property
    def semversion(self):
        return parse_blender_ver(self.subversion)

    @property
    def full_semversion(self):
        return BuildInfo.get_semver(self.subversion, self.branch, self.build_hash)

    @staticmethod
    @cache
    def get_semver(subversion, *s: str):
        v = parse_blender_ver(subversion)
        if not s:
            return v

        prerelease = ".".join(s_ for s_ in (v.prerelease, *s) if s_)
        return v.replace(prerelease=prerelease)

    @classmethod
    def from_dict(cls, path: Path, blinfo: dict):
        return cls(
            path.as_posix(),
            blinfo["subversion"],
            blinfo["build_hash"],
            datetime.strptime(blinfo["commit_time"], "%d-%b-%y-%H:%M").astimezone(),
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
                    "commit_time": self.commit_time.strftime("%d-%b-%y-%H:%M"),
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


def get_blender_ver_info(exe: Path) -> tuple[datetime, str, str, str]:
    version = _check_output([exe.as_posix(), "-v"]).decode("UTF-8")

    strptime = datetime.now(tz=timezone.utc)
    build_hash = ""
    subversion = ""
    custom_name = ""

    ctime = re.search("build commit time: (.*)", version)
    cdate = re.search("build commit date: (.*)", version)

    if ctime is not None and cdate is not None:
        strptime = datetime.strptime(
            f"{cdate[1].rstrip()} {ctime[1].rstrip()}",
            "%Y-%m-%d %H:%M",
        ).astimezone()
    if s := re.search("build hash: (.*)", version):
        build_hash = s[1].rstrip()

    if s := re.search("Blender (.*)", version):
        subversion = s[1].rstrip()
    else:
        s = version.splitlines()[0].strip()
        custom_name, subversion = s.rsplit(" ", 1)

    return (
        strptime,
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
        custom_executable=custom_exe,
    )


@dataclass(frozen=True)
class WriteBuildTask(Task):
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


def read_build_info(
    path: Path,
    archive_name: str | None = None,
    custom_exe: str | None = None,
    auto_write=True,
):
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
class ReadBuildTask(Task):
    path: Path
    archive_name: str | None = None
    version: Version | None = None
    custom_exe: str | None = None
    auto_write: bool = True

    finished = pyqtSignal(BuildInfo)
    failure = pyqtSignal(Exception)

    def run(self):
        try:
            auto_write = self.auto_write and self.version is None
            build_info = read_build_info(self.path, self.archive_name, self.custom_exe, auto_write)
            if self.version is not None:
                build_info.subversion = str(self.version)
                build_info.write_to(self.path)
            self.finished.emit(build_info)
        except Exception as e:
            self.failure.emit(e)
            raise

    def __str__(self):
        return f"Read build at {self.path}"
