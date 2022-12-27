from abc import ABCMeta, abstractmethod
import json
from typing import List, Optional


from pipeman.utils import LogUtils
from pipeman.version import SemanticVersion
from manifest import Manifest
from daemon.message import Message


class BaseWorkerConnection(metaclass=ABCMeta):
    # def __init__(self, id: str, coordinator: "coord.Coordinator") -> None:
    def __init__(self, id: str) -> None:
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        # self._coordinator = coordinator
        self._manifest: Optional[Manifest] = None
        self._id = id

    @property
    def id(self):
        return self._id

    def __repr__(self) -> str:
        return f"<Worker {self._id}>"

    @property
    def manifest(self) -> Optional[Manifest]:
        return self._manifest

    def on_msg(self, msg: Message):
        if msg.cmd == "response_manifest":
            manifest_json = msg.args[0]

            new_worker = False
            if self._manifest is None:
                new_worker = True

            last_name, last_version = None, None
            if self._manifest:
                last_name = self._manifest.name
                last_version = self._manifest.version.version_str
            json_content = json.loads(manifest_json)

            self._manifest = Manifest(json_content)

            if last_name and last_version:
                self._manifest.name = last_name
                self._manifest.version = SemanticVersion.from_version_str(last_version)

            if new_worker:
                self.logger.debug(f"New worker ready: {self._id}")
                # self._coordinator.scheduler.on_worker_ready(self)

            return new_worker

        elif msg.cmd == "done":
            component_id = msg.args[0]

            self.logger.debug(f"-{self._id}- Component {component_id} done")

            # self._coordinator.scheduler.cache_worker(self)
            # notify(self._coordinator.scheduler._is_pool_updated)

            # self._coordinator.task_monitor.record_component_done(component_id)

    def __iter__(self):
        yield ("name", str(self))
        yield ("id", self.id)
        yield (
            "manifest",
            json.loads(self.manifest.json(refresh=False)) if self.manifest else None,
        )

    @property
    def info_dict(self):
        return {
            "name": str(self),
            "worker_id": self.id,
            "manifest": json.loads(self.manifest.json(refresh=False))
            if self.manifest
            else None,
        }

    @abstractmethod
    async def exit(self):
        ...

    @abstractmethod
    async def execute(self, cmds: List[str]):
        ...


class WorkerConnectionInfo(BaseWorkerConnection):
    def __init__(self, id: str) -> None:
        super().__init__(id)

    async def exit(self):
        raise NotImplementedError

    async def execute(self, cmds: List[str]):
        raise NotImplementedError

    async def request_manifest(self):
        raise NotImplementedError

    async def send(self, msg: Message):
        raise NotImplementedError
