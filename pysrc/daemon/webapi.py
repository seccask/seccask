import asyncio
import json
import os
from typing import Any
from quart import Quart, make_response, websocket

import pipeman.utils as utils
from pipeman.env import env
from pipeman.config import default_config as conf

import daemon.coordinator as coord


class WebAPI:
    def __init__(
        self, loop: asyncio.AbstractEventLoop, coordinator: "coord.Coordinator"
    ) -> None:
        self._coordinator = coordinator
        self._loop = loop
        self._init_server()

    def _init_server(self):
        app = Quart(__name__)
        # app = cors(app, allow_origin="*", allow_headers="*")

        @app.route("/api")
        async def api():
            return {"hello": "world"}

        @app.route("/conf")
        async def sysconf():
            return await self.make_response(str(conf))

        @app.route("/pool")
        async def pool():
            return await self.make_response(self._coordinator.scheduler.pool_info_dict)

        @app.websocket("/pool_push")
        async def pool_push():
            async def sending():
                while True:
                    await self._coordinator.scheduler._is_pool_updated.get()
                    await websocket.send(
                        json.dumps(self._coordinator.scheduler.pool_info_dict)
                    )

            producer = asyncio.create_task(sending())
            consumer = asyncio.create_task(receiving())
            await asyncio.gather(producer, consumer)

        # @app.route("/pipelines")
        # async def pipelines():
        #     return await self.make_response(
        #         self._coordinator.task_monitor.pipelines_info_dict
        #     )

        # @app.websocket("/pipelines_push")
        # async def pipelines_push():
        #     async def sending():
        #         while True:
        #             await self._coordinator.task_monitor.wait("pipeline_update")
        #             await websocket.send(
        #                 json.dumps(self._coordinator.task_monitor.pipelines_info_dict)
        #             )

        #     producer = asyncio.create_task(sending())
        #     consumer = asyncio.create_task(receiving())
        #     await asyncio.gather(producer, consumer)

        # @app.route("/pipeline/<pipeline_hash>")
        # async def pipeline_info(pipeline_hash):
        #     return await self.make_response(
        #         self._coordinator.task_monitor.get_pipeline_info_dict(pipeline_hash)
        #     )

        @app.route("/logs")
        async def logs():
            return await self.make_response(utils.log_store, islist=True)

        @app.websocket("/logs_push")
        async def logs_push():
            async def sending():
                while True:
                    l = await utils.log_queue.get()
                    await websocket.send(json.dumps(l))

            producer = asyncio.create_task(sending())
            consumer = asyncio.create_task(receiving())
            await asyncio.gather(producer, consumer)

        async def receiving():
            while True:
                await websocket.receive()

        @app.route("/worker/<worker_id>")
        async def worker_info(worker_id):
            return await self.make_response(
                self._coordinator.get_worker_info(worker_id)
            )

        @app.route("/worker_log/<worker_id>")
        async def worker_log(worker_id):
            log_file = os.path.join(env.temp_path, f"{worker_id}.log")
            with open(log_file) as f:
                log = f.read()
            return await self.make_response({"id": worker_id, "log": log})

        # @app.route("/start_exp/<exp_name>")
        # async def start_exp(exp_name):
        #     success = self._coordinator._job_lock.acquire(blocking=False)
        #     if not success:
        #         return {"status": "err", "msg": "A job has already been started."}

        #     self._coordinator.emit_msg(Message("WebAPI", "start", [f"exp_{exp_name}"]))
        #     return {"status": "ok", "msg": f"Experiment {exp_name} started."}

        # self._app = app

    async def make_response(self, content: Any, islist=False):
        if islist:
            res = await make_response(json.dumps(list(reversed(content))))
        else:
            res = await make_response(content)

        res.headers["Access-Control-Allow-Origin"] = "*"

        if islist:
            res.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
            res.headers["X-Total-Count"] = f"{len(content)}"

        return res

    # def start(self):
    #     self._app.run(
    #         host=conf.get("coordinator", "host"),
    #         port=conf.getint("coordinator", "webapi_port"),
    #         loop=self._loop,
    #     )
