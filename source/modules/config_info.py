from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from modules.task import Task
from PyQt5.QtCore import pyqtSignal
from semver import Version

if TYPE_CHECKING:
    from pathlib import Path

# This is the version that started supporting the BLENDER_USER_RESOURCES environment variable
RESOURCES_SUPPORT_VER = Version(3, 4, 0)


@dataclass
class ConfigInfo:
    file_version = "1.0"

    directory: Path
    target_version: Version | None
    name: str

    def __eq__(self, other: ConfigInfo):
        return self.directory == other.directory and self.target_version == other.target_version

    def get_env(self, v: Version | None = None) -> dict[str, str]:
        env = {
            "BLENDER_USER_CONFIG": str(self.directory / "config"),
            "BLENDER_USER_SCRIPTS": str(self.directory / "scripts"),
            "BLENDER_USER_EXTENSIONS": str(self.directory / "extensions"),
            "BLENDER_USER_DATAFILES": str(self.directory / "datafiles"),
        }

        if v is not None and v >= RESOURCES_SUPPORT_VER:
            env = {"BLENDER_USER_RESOURCES": str(self.directory)}

        return env

    @classmethod
    def from_dict(cls, directory: Path, confinfo: dict):
        v = confinfo.get("target_version")

        if v is not None:
            v = Version.parse(v)

        return cls(
            directory,
            v,
            confinfo["name"],
        )

    def to_dict(self):
        return {
            "file_version": self.__class__.file_version,
            "target_version": str(self.target_version),
            "name": self.name,
        }

    def write(self):
        data = self.to_dict()
        blinfo = self.directory / ".confinfo"
        with blinfo.open("w", encoding="utf-8") as file:
            json.dump(data, file)
        return data


@dataclass(frozen=True)
class ReadConfigTask(Task):
    path: Path

    finished = pyqtSignal(ConfigInfo)
    failure = pyqtSignal(Exception)

    def run(self):
        cinfo = self.path / ".confinfo"
        if not cinfo.exists():
            raise FileNotFoundError(cinfo)

        with cinfo.open("r") as f:
            info = ConfigInfo.from_dict(self.path, json.load(f))
            self.finished.emit(info)
