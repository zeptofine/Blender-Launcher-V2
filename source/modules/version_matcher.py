from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from functools import cache
from operator import attrgetter
from typing import TYPE_CHECKING

from semver import Version

if TYPE_CHECKING:
    from collections.abc import Sequence

    from modules.build_info import BuildInfo


@dataclass(frozen=True)
class BasicBuildInfo:
    version: Version
    branch: str
    commit_time: datetime.datetime

    @property
    def major(self):
        return self.version.major

    @property
    def minor(self):
        return self.version.minor

    @property
    def patch(self):
        return self.version.patch

    def __lt__(self, other: BasicBuildInfo):
        if self.version == other.version:
            return self.commit_time < other.commit_time

        return self.version < other.version

    @classmethod
    def from_buildinfo(cls, buildinfo: BuildInfo):
        return BasicBuildInfo(
            version=buildinfo.full_semversion, commit_time=buildinfo.commit_time, branch=buildinfo.branch
        )


# ^   | match the largest number in that column
# *   | match any number in that column
# -   | match the smallest number in that column
# <n> | match a number in that column

VERSION_SEARCH_REGEX = re.compile(r"^([\^\-\*]|\d+).([\^\-\*]|\d+)(.([\^\-\*]|\d+))?$")

VALID_QUERIES = """^.^.*
*.*.14
*.*.*
^.*.*
-.*.^
4.2"""


@cache
def _parse(s: str) -> tuple[int | str, int | str, int | str]:
    """Parse a query from a string. does not support branch and commit_time"""
    match = VERSION_SEARCH_REGEX.match(s)
    if not match:
        raise ValueError(f"Invalid version search query: {s}")

    major = match.group(1)
    minor = match.group(2)
    patch = match.group(4)

    if major.isnumeric():
        major = int(major)
    if minor.isnumeric():
        minor = int(minor)
    if patch is not None and patch.isnumeric():
        patch = int(patch)
    if patch is None:
        patch = "*"

    return major, minor, patch


@dataclass(frozen=True)
class VersionSearchQuery:
    """A dataclass for a search query. The attributes are ordered by priority"""

    major: int | str
    minor: int | str
    patch: int | str
    branch: str | None = None
    commit_time: datetime.datetime | str | None = None

    def __post_init__(self):
        for pos in (self.major, self.minor, self.patch, self.commit_time):
            if isinstance(pos, str) and pos not in ["^", "*", "-"]:
                raise ValueError(f'{pos} must be in ["^", "*", "-"]')

    @classmethod
    def parse(cls, s: str):
        """Parse a query from a string. does not support branch and commit_time"""

        return cls(*_parse(s))

    @classmethod
    def default(cls):
        return cls("^", "^", "^", commit_time="^", branch=None)

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self):
        return f"{self.__class__.__name__}(major={self.major}, minor={self.minor}, patch={self.patch})"


# Examples:
# VersionSearchQuery("^", "^", "^"): Match the latest version(s)
# VersionSearchQuery(4, "^", "^"): Match the latest version of major 4
# VersionSearchQuery("^", "*", "*"): Match any version in the latest major release


@dataclass(frozen=True)
class BInfoMatcher:
    versions: tuple[BasicBuildInfo, ...]

    def match(self, s: VersionSearchQuery) -> tuple[BasicBuildInfo, ...]:
        versions = self.versions

        for place in ("major", "minor", "patch", "branch", "commit_time"):
            getter = attrgetter(place)
            p: str | int | datetime.datetime | None = getter(s)
            if p == "^":
                # get the max number for `place` in version
                max_p = max(getter(v) for v in versions)

                versions = [v for v in versions if getter(v) == max_p]
            elif p == "*" or p is None:
                pass  # all versions match
            elif p == "-":
                # get the min number for `place` in version
                min_p = min(getter(v) for v in versions)

                versions = [v for v in versions if getter(v) == min_p]
            else:
                versions = [v for v in versions if getter(v) == p]

            if len(versions) == 1:
                return tuple(versions)

        return tuple(versions)


if __name__ == "__main__":  # Test BInfoMatcher
    utc = datetime.timezone.utc

    def test_binfo_matcher():
        builds = (
            BasicBuildInfo(Version.parse("1.2.3"), "stable", datetime.datetime(2020, 5, 4, tzinfo=utc)),
            BasicBuildInfo(Version.parse("1.2.2"), "stable", datetime.datetime(2020, 4, 2, tzinfo=utc)),
            BasicBuildInfo(Version.parse("1.2.1"), "daily", datetime.datetime(2020, 3, 1, tzinfo=utc)),
            BasicBuildInfo(Version.parse("1.2.4"), "stable", datetime.datetime(2020, 6, 3, tzinfo=utc)),
            BasicBuildInfo(Version.parse("3.6.14"), "lts", datetime.datetime(2024, 7, 16, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.2.0"), "stable", datetime.datetime(2024, 7, 16, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.3.0"), "daily", datetime.datetime(2024, 7, 30, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.3.0"), "daily", datetime.datetime(2024, 7, 28, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.3.1"), "daily", datetime.datetime(2024, 7, 20, tzinfo=utc)),
        )
        matcher = BInfoMatcher(builds)

        # find the latest major builds with any patch number
        results = matcher.match(VersionSearchQuery("^", "^", "*"))
        assert results == (
            BasicBuildInfo(Version.parse("4.3.0"), "daily", datetime.datetime(2024, 7, 30, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.3.0"), "daily", datetime.datetime(2024, 7, 28, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.3.1"), "daily", datetime.datetime(2024, 7, 20, tzinfo=utc)),
        )

        # find any version with a patch of 14
        results = matcher.match(VersionSearchQuery("*", "*", 14))
        assert results == (BasicBuildInfo(Version.parse("3.6.14"), "lts", datetime.datetime(2024, 7, 16, tzinfo=utc)),)

        # find any version in the lts branch
        results = matcher.match(VersionSearchQuery("*", "*", "*", branch="lts"))
        assert results == (BasicBuildInfo(Version.parse("3.6.14"), "lts", datetime.datetime(2024, 7, 16, tzinfo=utc)),)

        # find the latest daily builds for the latest major release
        results = matcher.match(VersionSearchQuery("^", "*", "*", branch="daily", commit_time="^"))
        assert results == (BasicBuildInfo(Version.parse("4.3.0"), "daily", datetime.datetime(2024, 7, 30, tzinfo=utc)),)

        # find oldest major release with any minor and largest patch
        results = matcher.match(VersionSearchQuery("-", "*", "^"))
        assert results == (BasicBuildInfo(Version.parse("1.2.4"), "stable", datetime.datetime(2020, 6, 3, tzinfo=utc)),)

        print("test_binfo_matcher successful!")

    def test_search_query_parser():
        # Test parsing of search query strings
        assert VersionSearchQuery.parse("1.2.3") == VersionSearchQuery(1, 2, 3)
        assert VersionSearchQuery.parse("^.^.*") == VersionSearchQuery("^", "^", "*")
        assert VersionSearchQuery.parse("*.*.*") == VersionSearchQuery("*", "*", "*")
        assert VersionSearchQuery.parse("^.*.*") == VersionSearchQuery("^", "*", "*")
        assert VersionSearchQuery.parse("-.*.^") == VersionSearchQuery("-", "*", "^")
        assert VersionSearchQuery.parse("*.*.14") == VersionSearchQuery("*", "*", 14)
        assert VersionSearchQuery.parse("4.2") == VersionSearchQuery(4, 2, "*")
        # Test parsing of search query strings that are not valid
        try:
            VersionSearchQuery.parse("abc")
            raise AssertionError("Expected ValueError to be raised")
        except ValueError:
            pass

        print("test_search_query_parser successful!")

    test_binfo_matcher()
    test_search_query_parser()
