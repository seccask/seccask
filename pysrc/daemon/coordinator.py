import asyncio
import itertools
import json
import datetime
import os
import time
from typing import Dict, List, Literal

from pipeman.env import env
from pipeman.utils import LogUtils, first, notify
import pipeline as p


json.JSONEncoder.default = lambda _, obj: (  # type: ignore
    obj.isoformat() if isinstance(obj, datetime.datetime) else None
)


def on_new_lifecycle(manifest_name: str):
    """New ML lifecycle"""
    import exp_runner

    manifest_path = os.path.abspath(
        os.path.join(env.home, "exp", f"{manifest_name}.yaml")
    )

    logger = LogUtils.get_default_named_logger("ExpRunner")
    logger.debug(f"Starting Experiment {manifest_path}...")

    exp_runner.start(manifest_path)


class TaskMonitor:
    PUBLISHERS = Literal["pipeline_update"]

    def __init__(self) -> None:
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self._dummy_pipeline = None
        self._active_pipeline: p.Pipeline = self.get_dummy_pipeline()
        self._finished_pipelines: List[p.Pipeline] = []
        self._pending_components: Dict[str, p.Component] = {}
        self._pipeline_update_publisher = asyncio.Queue(1)

    def notify(self, publisher: PUBLISHERS):
        p = None
        if publisher == "pipeline_update":
            p = self._pipeline_update_publisher

        notify(p)

    async def wait(self, publisher: PUBLISHERS):
        p = None
        if publisher == "pipeline_update":
            p = self._pipeline_update_publisher

        await p.get()

    def get_dummy_pipeline(self):
        if not self._dummy_pipeline:
            self._dummy_pipeline = p.Pipeline(
                name="DUMMY", version="DUMMY", components=[]
            )
        return self._dummy_pipeline

    @property
    def active_pipeline(self):
        return self._active_pipeline

    @property
    def pending_components(self):
        return self._pending_components

    @active_pipeline.setter
    def active_pipeline(self, active_pipeline: "p.Pipeline"):
        self._active_pipeline = active_pipeline

    def record_component_done(self, component_id: str):
        component = self._pending_components[component_id]
        component.done = True
        component.end_time = int(time.time() * 1000)
        # self.notify("pipeline_update")

        if component.is_end_of_sequence:
            self._on_pipeline_done()

        if component.lock is not None:
            component.lock.release()

    def _on_pipeline_done(self):
        self.logger.debug(f"Pipeline done")
        self._finished_pipelines.append(self._active_pipeline)
        self._active_pipeline = self.get_dummy_pipeline()
        # self.notify("pipeline_update")

    def add_pending_components(self, components: Dict[str, "p.Component"]):
        self._pending_components.update(components)

    @property
    def pipelines_info_dict(self):
        return {
            "active": self._active_pipeline.info_dict,
            "finished": list(
                map(lambda x: x.info_dict, reversed(self._finished_pipelines))
            ),
        }

    def get_pipeline_info_dict(self, pipeline_hash: str):
        return first(
            itertools.chain([self._active_pipeline], self._finished_pipelines),
            condition=lambda p: p.hash == pipeline_hash,
            default=None,
        ).info_dict
