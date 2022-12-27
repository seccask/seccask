from configparser import ConfigParser
import hashlib
import os
import threading
import tempfile
from typing import List, Optional

from pipeman.meta import LibraryMeta
from manifest import ComponentType, Manifest
from daemon.worker import execute_component
import workerconn as wc


class DAGNode:
    def __init__(self) -> None:
        self._parents: List["DAGNode"] = []
        self._children: List["DAGNode"] = []

    @property
    def parents(self):
        return self.parents

    @property
    def children(self):
        return self._children

    @property
    def is_end_of_sequence(self):
        return len(self.children) == 0


class Component(DAGNode):
    def __init__(
        self,
        name: str,
        id: str,
        path: Optional[str] = None,
        inputfolder: str = "",
        load_manifest: bool = False,
    ) -> None:
        super().__init__()
        self._name = name
        self._done = True if name.startswith("dataset") else False
        self._path = path
        self._inputfolder = inputfolder
        self._start_time = -1
        self._end_time = -1
        self._id = id
        self._worker = None
        self._lock = None
        self._manifest = None
        self._command = None
        if load_manifest:
            self._manifest = Manifest.load(self.manifest_path)

    @property
    def command(self):
        return self._command

    @command.setter
    def command(self, command: List[str]):
        self._command = command

    @property
    def lock(self):
        return self._lock

    @lock.setter
    def lock(self, lock: threading.Lock):
        self._lock = lock

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path: str):
        self._path = path
        self._manifest = Manifest.load(self.manifest_path)

    @property
    def done(self):
        return self._done

    @done.setter
    def done(self, done: bool):
        self._done = done

    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self, value: int):
        self._start_time = value

    @property
    def end_time(self):
        return self._end_time

    @end_time.setter
    def end_time(self, value: int):
        self._end_time = value

    @property
    def worker(self):
        return self._worker

    @worker.setter
    def worker(self, worker: "wc.BaseWorkerConnection"):
        self._worker = worker

    def __iter__(self):
        yield ("id", self.id)
        yield ("name", self.name)
        yield ("done", self.done)
        yield ("start_time", self.start_time)
        yield ("end_time", self.end_time)
        if self.worker is not None:
            yield ("worker", self.worker.info_dict)
        if self.path is not None:
            yield ("manifest", dict(self.get_manifest()))

    @property
    def manifest_path(self) -> str:
        if not self._path:
            raise AssertionError("Component path not specified")
        return os.path.join(self._path, ".manifest.v2.yaml")

    def get_manifest(self, refresh: bool = False):
        if self.path is None:
            raise AssertionError("Component path not specified")

        if self._manifest is None or refresh:
            execute_component(
                component_id="DUMMY",
                working_directory=self.path,
                cmds=self.get_component_commands(),
            )
            manifest = Manifest.capture_current_env()
            manifest.name = self._meta.name
            manifest.type = ComponentType(self._meta.meta_type)
            manifest.version = self._meta.version

            # self._cleanup()

            self._manifest = manifest

        return self._manifest

    def get_component_commands(self) -> List[str]:
        if not self._path:
            raise AssertionError("Component path not specified")

        cp = ConfigParser()
        cp.read(os.path.join(self._path, ".manifest"))
        self._meta = LibraryMeta(cp)
        self._temp_output_folder = tempfile.mkdtemp(prefix=".")
        return [
            "python",
            self._meta.train_script,
            "--input",
            self._inputfolder,
            "--output",
            self._temp_output_folder,
        ]

    def write_manifest(self) -> None:
        manifest = self.get_manifest(refresh=True)
        manifest.dump(self.manifest_path)

    def _cleanup(self):
        if self._temp_output_folder:
            import shutil

            shutil.rmtree(self._temp_output_folder)
            del self._temp_output_folder
            self._temp_output_folder = None

    def __repr__(self) -> str:
        return f"<Component {self.id}>"


class Pipeline(DAGNode):
    def __init__(self, name: str, version: str, components: List[Component]) -> None:
        super().__init__()
        self._name = name
        self._done = False
        self._version = version
        self._components = components

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def done(self):
        return self._done

    @done.setter
    def done(self, done: bool):
        self._done = done

    @property
    def components(self):
        return self._components

    @property
    def hash(self):
        if len(self.components) == 0:
            return None

        hash = hashlib.sha256()
        hash.update(f"{self.components[0].start_time}".encode("utf-8"))
        hash.update(" ".join([p.name for p in self.components]).encode("utf-8"))
        return hash.hexdigest()

    def __iter__(self):
        yield ("name", self.name)
        yield ("version", self.version)
        yield ("done", self.done)

    @property
    def info_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "pipeline_hash": self.hash,
            "done": self.done,
            "components": [dict(c) for c in self.components],
        }


if __name__ == "__main__":
    import sys
    import pathlib

    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} COMPONENT_PATH INPUT_FOLDER")
        sys.exit(1)

    component_path = sys.argv[1]
    inputfolder = sys.argv[2]
    component_name = pathlib.PurePath(component_path).name

    c = Component(
        name=component_name,
        id=component_name,
        path=component_path,
        inputfolder=inputfolder,
        load_manifest=False,
    )
    c.write_manifest()
    print(c.get_manifest(refresh=False).json())
