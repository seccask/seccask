# Python 3.7 only
import re


class SemanticVersion:
    DEFAULT_BRANCH = "master"
    REGEX_VERSION_STR = r"(\S+)\.(\d+)\.(\d+)"

    def __init__(self, branch: str, api_version: int, inc_version: int):
        self._branch = branch
        self._api_version = api_version
        self._inc_version = inc_version

    @property
    def default_branch(self):
        return self.DEFAULT_BRANCH

    @property
    def branch(self) -> str:
        return self._branch

    @branch.setter
    def branch(self, val: str):
        self._branch = val

    @property
    def api_version(self) -> int:
        return self._api_version

    @api_version.setter
    def api_version(self, val: int):
        self._api_version = val

    @property
    def inc_version(self) -> int:
        return self._inc_version

    @inc_version.setter
    def inc_version(self, val: int):
        self._inc_version = val

    @property
    def version_str(self) -> str:
        return f"{self.branch}.{self.api_version}.{self.inc_version}"

    @classmethod
    # def from_version_str(cls, version: str) -> SemanticVersion:
    def from_version_str(cls, version: str):
        result = re.match(cls.REGEX_VERSION_STR, version)
        if result is None:
            raise RuntimeError(f"Regex parse error: applying {cls.REGEX_VERSION_STR} on {version}")
        return SemanticVersion(result.group(1), int(result.group(2)), int(result.group(3)))

    @classmethod
    # def build_zero_version(cls) -> SemanticVersion:
    def build_zero_version(cls):
        return SemanticVersion(cls.DEFAULT_BRANCH, 0, 0)

    def equals(self, sv):
        return (
            self.branch == sv.branch
            and self.api_version == sv.api_version
            and self.inc_version == sv.inc_version
        )
