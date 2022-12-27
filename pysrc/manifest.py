"""Component Manifest Manager.
"""
import json
from enum import Enum
import yaml
import hashlib
from typing import Any, Dict, Optional

from pipeman.version import SemanticVersion
import package


class ComponentType(Enum):
    DATASET = "dataset"
    LIBRARY = "library"


class Manifest:
    DEFAULT_VALUES = {
        "name": "DUMMY",
        "type": ComponentType.DATASET,
        "version": SemanticVersion.build_zero_version(),
        "packages_semver": False,
        "packages": {},
    }

    def __init__(self, obj: Optional[dict] = None) -> None:
        if obj is not None:
            self._name = obj["name"] if "name" in obj else self.DEFAULT_VALUES["name"]
            self._type = (
                ComponentType(obj["type"])
                if "type" in obj
                else self.DEFAULT_VALUES["type"]
            )
            self._version = (
                SemanticVersion.from_version_str(obj["version"])
                if "version" in obj
                else self.DEFAULT_VALUES["version"]
            )
            self._packages_semver = (
                obj["packages_semver"]
                if "packages_semver" in obj
                else self.DEFAULT_VALUES["packages_semver"]
            )
            self._packages = (
                obj["packages"]
                if "packages" in obj
                else self.DEFAULT_VALUES["packages"]
            )
        else:
            self._name = self.DEFAULT_VALUES["name"]
            self._type = self.DEFAULT_VALUES["type"]
            self._version = self.DEFAULT_VALUES["version"]
            self._packages_semver = self.DEFAULT_VALUES["packages_semver"]
            self._packages = self.DEFAULT_VALUES["packages"]

        self.appendix: Any = None

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        self._name = name

    @property
    def type(self) -> ComponentType:
        return self._type

    @type.setter
    def type(self, type: ComponentType):
        self._type = type

    @property
    def version(self) -> SemanticVersion:
        return self._version

    @version.setter
    def version(self, version: SemanticVersion):
        self._version = version

    @property
    def packages_semver(self) -> bool:
        return self._packages_semver

    @packages_semver.setter
    def packages_semver(self, packages_semver: bool):
        self._packages_semver = packages_semver

    @property
    def packages(self) -> Dict[str, str]:
        return self._packages

    def update_packages(self):
        self._packages = package.get_active_packages()

    @property
    def packages_hash(self) -> str:
        sha256 = hashlib.sha256()
        sha256.update(json.dumps(self.packages, sort_keys=True).encode("utf-8"))
        # ! To better test hash matching, add some noise here
        sha256.update(self._name.encode("utf-8"))
        return sha256.hexdigest()

    def __iter__(self):
        yield ("name", self.name)
        yield ("type", self.type.value)
        yield ("version", self.version.version_str)

        if self.type == ComponentType.LIBRARY:
            yield ("packages_semver", self.packages_semver)
            yield ("hash", self.packages_hash)
            yield ("packages", self.packages)

        if self.appendix:
            for k, v in self.appendix.items():
                yield (k, v)

    def json(self, refresh=True) -> str:
        if refresh:
            self.capture_current_env()
        return json.dumps(dict(self), sort_keys=True)

    def __repr__(self):
        if self.type == ComponentType.DATASET:
            return "<Dataset Manifest name: %s, version: %s>" % (
                self.name,
                self.version.version_str,
            )
        else:
            return (
                "<Library Manifest name: %s, version: %s, packages_semver: %s, packages_hash: %s, packages: %s>"
                % (
                    self.name,
                    self.version.version_str,
                    self.packages_semver,
                    self.packages_hash,
                    self.packages,
                )
            )

    @staticmethod
    def load(path: str):
        with open(path, "r") as f:
            obj = yaml.safe_load(f)
        return Manifest(obj)

    def dump(self, path: str):
        with open(path, "w") as f:
            yaml.safe_dump(dict(self), f)

    @staticmethod
    def capture_current_env(appendix: Any = None):
        """Call this function in a component enclave to fetch all manifest information.
        This does not set name and version.
        """
        manifest = Manifest()
        manifest.type = ComponentType.LIBRARY
        manifest.packages_semver = False
        manifest.update_packages()

        manifest.appendix = appendix

        return manifest


if __name__ == "__main__":
    from pprint import pprint

    # pprint(Manifest.load("manifest_example_library.yaml"))
    # pprint(Manifest.capture_current_env())
    manifest = Manifest.load("manifest_example_library.yaml")
    print(manifest.json())
