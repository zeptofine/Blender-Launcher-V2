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
    build_hash: str
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
            version=buildinfo.full_semversion,
            branch=buildinfo.branch,
            build_hash=buildinfo.build_hash if buildinfo.build_hash is not None else "",
            commit_time=buildinfo.commit_time,
        )


# ^   | match the largest number in that column
# *   | match any number in that column
# -   | match the smallest number in that column
# <n> | match a number in that column

VERSION_SEARCH_REGEX = re.compile(r"^([\^\-\*]|\d+)(.([\^\-\*]|\d+))?(.([\^\-\*]|\d+))?$")

VALID_QUERIES = """^.^.*
*.*.14
*.*.*
^.*.*
-.*.^
4.2
3"""


@cache
def _parse(s: str) -> tuple[int | str, int | str, int | str]:
    """Parse a query from a string. does not support branch and commit_time"""
    match = VERSION_SEARCH_REGEX.match(s)
    if not match:
        raise ValueError(f"Invalid version search query: {s}")

    major = match.group(1)
    minor = match.group(3)
    patch = match.group(5)

    if major.isnumeric():
        major = int(major)
    if minor is not None and minor.isnumeric():
        minor = int(minor)
    if minor is None:
        minor = "*"
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
    build_hash: str | None = None
    commit_time: datetime.datetime | str | None = None

    def __post_init__(self):
        for pos in (self.major, self.minor, self.patch, self.commit_time):
            if isinstance(pos, str) and pos not in ["^", "*", "-"]:
                raise ValueError(f'{pos} must be in ["^", "*", "-"]')
        if self.build_hash and self.build_hash in ["^", "-"]:
            raise ValueError("build_hash cannot be temporally matched")
        if self.branch and self.branch in ["^", "-"]:
            raise ValueError("branch cannot be temporally matched")

    @classmethod
    def parse(cls, s: str):
        """Parse a query from a string. does not support branch and commit_time"""

        return cls(*_parse(s))

    @classmethod
    def default(cls):
        return cls("^", "^", "^", commit_time="^", branch=None)

    def to_dict(self):
        return {
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "branch": self.branch,
            "build_hash": self.build_hash,
            "commit_time": self.commit_time.isoformat()
            if isinstance(self.commit_time, datetime.datetime)
            else self.commit_time,
        }

    @classmethod
    def from_dict(cls, d: dict):
        try:
            dt = datetime.datetime.fromisoformat(d["commit_time"])
        except (TypeError, ValueError):
            dt = d["commit_time"]

        d["commit_time"] = dt

        return cls(**d)

    def with_branch(self, branch: str | None = None):
        return self.__class__(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            branch=branch,
            commit_time=self.commit_time,
        )

    def with_build_hash(self, build_hash: str | None = None):
        return self.__class__(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            branch=self.branch,
            commit_time=self.commit_time,
            build_hash=build_hash,
        )

    def with_commit_time(self, commit_time: datetime.datetime | str | None = None):
        return self.__class__(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            branch=self.branch,
            commit_time=commit_time,
        )

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"


# Examples:
# VersionSearchQuery("^", "^", "^"): Match the latest version(s)
# VersionSearchQuery(4, "^", "^"): Match the latest version of major 4
# VersionSearchQuery("^", "*", "*"): Match any version in the latest major release


@dataclass(frozen=True)
class BInfoMatcher:
    versions: tuple[BasicBuildInfo, ...]

    def match(self, s: VersionSearchQuery) -> tuple[BasicBuildInfo, ...]:
        versions = self.versions

        for place in ("major", "minor", "patch", "branch", "build_hash", "commit_time"):
            from pprint import pprint

            # print("VERSIONS:")
            # pprint(versions)
            # print(f"PLACE: {place}")
            getter = attrgetter(place)
            p: str | int | datetime.datetime | None = getter(s)
            # print(f"MATCHING: {p!r}")
            if p == "^":
                # get the max number for `place` in version
                max_p = max(getter(v) for v in versions)

                versions = [v for v in versions if getter(v) == max_p]
            elif p == "*" or p is None:
                continue  # all versions match
            elif p == "-":
                # get the min number for `place` in version
                min_p = min(getter(v) for v in versions)

                versions = [v for v in versions if getter(v) == min_p]
            else:
                versions = [v for v in versions if getter(v) == p]

            if len(versions) == 1:
                return tuple(versions)
            if not versions:
                return ()

        return tuple(versions)


if __name__ == "__main__":  # Test BInfoMatcher
    utc = datetime.timezone.utc

    builds = (
        BasicBuildInfo(Version.parse("1.2.3"), "stable", "", datetime.datetime(2020, 5, 4, tzinfo=utc)),
        BasicBuildInfo(Version.parse("1.2.2"), "stable", "", datetime.datetime(2020, 4, 2, tzinfo=utc)),
        BasicBuildInfo(Version.parse("1.2.1"), "daily", "", datetime.datetime(2020, 3, 1, tzinfo=utc)),
        BasicBuildInfo(Version.parse("1.2.4"), "stable", "", datetime.datetime(2020, 6, 3, tzinfo=utc)),
        BasicBuildInfo(Version.parse("3.6.14"), "lts", "", datetime.datetime(2024, 7, 16, tzinfo=utc)),
        BasicBuildInfo(Version.parse("4.2.0"), "stable", "", datetime.datetime(2024, 7, 16, tzinfo=utc)),
        BasicBuildInfo(Version.parse("4.3.0"), "daily", "", datetime.datetime(2024, 7, 30, tzinfo=utc)),
        BasicBuildInfo(Version.parse("4.3.0"), "daily", "", datetime.datetime(2024, 7, 28, tzinfo=utc)),
        BasicBuildInfo(Version.parse("4.3.1"), "daily", "", datetime.datetime(2024, 7, 20, tzinfo=utc)),
    )

    matcher = BInfoMatcher(builds)

    def test_binfo_matcher():
        # find the latest minor builds with any patch number
        results = matcher.match(VersionSearchQuery("^", "^", "*"))
        assert results == (
            BasicBuildInfo(Version.parse("4.3.0"), "daily", "", datetime.datetime(2024, 7, 30, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.3.0"), "daily", "", datetime.datetime(2024, 7, 28, tzinfo=utc)),
            BasicBuildInfo(Version.parse("4.3.1"), "daily", "", datetime.datetime(2024, 7, 20, tzinfo=utc)),
        )

        # find any version with a patch of 14
        results = matcher.match(VersionSearchQuery("*", "*", 14))
        assert results == (
            BasicBuildInfo(Version.parse("3.6.14"), "lts", "", datetime.datetime(2024, 7, 16, tzinfo=utc)),
        )

        # find any version in the lts branch
        results = matcher.match(VersionSearchQuery("*", "*", "*", branch="lts"))
        assert results == (
            BasicBuildInfo(Version.parse("3.6.14"), "lts", "", datetime.datetime(2024, 7, 16, tzinfo=utc)),
        )

        # find the latest daily builds for the latest major release
        results = matcher.match(VersionSearchQuery("^", "*", "*", branch="daily", commit_time="^"))
        assert results == (
            BasicBuildInfo(Version.parse("4.3.0"), "daily", "", datetime.datetime(2024, 7, 30, tzinfo=utc)),
        )

        # find oldest major release with any minor and largest patch
        results = matcher.match(VersionSearchQuery("-", "*", "^"))
        assert results == (
            BasicBuildInfo(Version.parse("1.2.4"), "stable", "", datetime.datetime(2020, 6, 3, tzinfo=utc)),
        )

        print("test_binfo_matcher successful!")

    def test_vsq_serialization():
        import json

        for query in (
            VersionSearchQuery("^", "^", "*"),
            VersionSearchQuery("*", "*", 14),
            VersionSearchQuery("*", "*", "*", branch="lts"),
            VersionSearchQuery("^", "*", "*", branch="daily", commit_time="^"),
            VersionSearchQuery("-", "*", "^"),
            VersionSearchQuery(4, 0, 0),
            VersionSearchQuery(4, "*", "*"),
            VersionSearchQuery("^", "^", "*", branch="stable", commit_time=datetime.datetime(2020, 5, 4, tzinfo=utc)),
        ):
            result_before_serialization = matcher.match(query)

            serialized_query = json.dumps(query.to_dict())
            deserialized_query = VersionSearchQuery.from_dict(json.loads(serialized_query))

            result_after_serialization = matcher.match(deserialized_query)

            assert result_before_serialization == result_after_serialization

        print("test_vsq_serialization successful!")

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
    test_vsq_serialization()
    test_search_query_parser()
