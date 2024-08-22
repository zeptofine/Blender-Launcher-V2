from __future__ import annotations

import json
import string
import uuid
from dataclasses import dataclass
from pathlib import Path

from modules.task import Task
from PyQt5.QtCore import pyqtSignal
from semver import Version

# This is the version that started supporting the BLENDER_USER_RESOURCES environment variable
# (according to the docs)
RESOURCES_SUPPORT_VER = Version(3, 4, 0)


@dataclass(frozen=True)
class ConfigInfo:
    file_version = "1.0"

    directory: Path
    target_version: Version | None
    name: str

    def __eq__(self, other: ConfigInfo):
        return self.directory == other.directory and self.target_version == other.target_version

    def get_env(self, v: Version | None = None) -> dict[str, str]:
        if v is not None and v >= RESOURCES_SUPPORT_VER:
            return {"BLENDER_USER_RESOURCES": str(self.directory)}

        return {
            "BLENDER_USER_CONFIG": str(self.directory / "config"),
            "BLENDER_USER_SCRIPTS": str(self.directory / "scripts"),
            "BLENDER_USER_EXTENSIONS": str(self.directory / "extensions"),
            "BLENDER_USER_DATAFILES": str(self.directory / "datafiles"),
        }

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

    @classmethod
    def from_path(cls, directory: Path):
        """
        Creates a default ConfigInfo from a directory. Does not store
        a target version and assumes the name from the path stem.
        """
        return cls(directory=directory, target_version=None, name=directory.stem)

    def to_dict(self):
        return {
            "file_version": self.__class__.file_version,
            "target_version": str(self.target_version),
            "name": self.name,
        }

    def write(self):
        data = self.to_dict()
        self.directory.mkdir(parents=True, exist_ok=True)
        blinfo = self.directory / ".confinfo"
        with blinfo.open("w", encoding="utf-8") as file:
            json.dump(data, file)
        return data


def read_config(path: Path):
    cinfo = path / ".confinfo"
    if not cinfo.exists():  # Create a default info
        return ConfigInfo.from_path(path)

    with cinfo.open("r") as f:
        return ConfigInfo.from_dict(path, json.load(f))


VALID_CHARS_IN_CONFIG_DIR = string.ascii_letters + string.digits + "+-._"


def sanitize_pathname(s: str):
    return "".join(c for c in s.replace(" ", "-") if c in VALID_CHARS_IN_CONFIG_DIR)


def config_path_name(s: str) -> Path:
    s = sanitize_pathname(s)

    # add a uuid to prevent future collisions
    path_id = str(uuid.uuid1()).split("-", 1)[0]
    s = f"{s}-{path_id}"

    return Path(s)
