import asyncio
import itertools
import os
import time
import uuid
from typing import Callable, MutableSet, Optional

import paramiko
import yaml

from pipeman.env import env
from pipeman.store.ustoreconf import UStoreConf
from pipeman.config import default_config as conf
from pipeman.utils import LogUtils
from pipeman.version import SemanticVersion
import pipeline as p
import worker_cache as cache
import workerconn as wc

import cpp_coordinator


class WorkerPoolFull(Exception):
    pass


class Scheduler:
    def __init__(
        self, num_slot: int = conf.getint("scheduler", "default_num_slot")
    ) -> None:
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)

        self._active_workers: cache.LRUCache = cache.LRUCache()
        self._cached_workers: cache.LRUCache = cache.LRUCache()
        # self._active_workers = cache.PACache()
        # self._cached_workers = cache.PACache()
        self._new_workers = []
        self._num_slot = num_slot
        # self._waiting_components: MutableSet[Tuple[p.Component, asyncio.Future]] = set()
        self._waiting_components: MutableSet[p.Component] = set()

        self._is_pool_updated = asyncio.Queue(1)

        self._connect_ssh()

    @property
    def active_workers(self):
        return self._active_workers

    @property
    def cached_workers(self):
        return self._cached_workers

    @property
    def new_workers(self):
        return self._new_workers

    def add_new_worker(self, worker: "wc.BaseWorkerConnection"):
        self._new_workers.append(worker)

    def get_worker(self, id: str) -> Optional["wc.BaseWorkerConnection"]:
        for w in itertools.chain(
            self._new_workers, self._active_workers, self._cached_workers
        ):
            if w.id == id:
                return w

    def _connect_ssh(self):
        config = UStoreConf()

        ssh_key = paramiko.RSAKey.from_private_key_file(config.USTORE_KEY_PATH)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ## Use password
        # ssh_client.connect(
        #     hostname=self.config.USTORE_ADDR,
        #     username=self.config.USTORE_USERNAME,
        #     password="PASSWORD",
        # )

        ## Use publickey
        ssh_client.connect(
            hostname=config.USTORE_ADDR, username=config.USTORE_USERNAME, pkey=ssh_key
        )
        self.sshclient = ssh_client

    @property
    def pool_info_dict(self):
        return {
            "active": [w.info_dict for w in self.active_workers],
            "cached": [w.info_dict for w in self.cached_workers],
        }

    def _print_workers(self):
        self.logger.debug(
            f"Active: {self._active_workers}; Cached: {self._cached_workers}"
        )

    def _execute_new_worker_command(self):
        id = str(uuid.uuid4())
        temp_file_name = os.path.join(env.temp_path, f"{id}.log")
        # strace_file_name = os.path.join(env.temp_path, f"strace-{id}.txt")
        self.logger.debug(f"Creating new worker. CLI output to {temp_file_name}")

        section_name = "worker_sgx" if conf.is_sgx_enabled else "worker"

        """Use SecCask 2 binary"""
        # cmds_template = (
        #     r"ltrace -fS -o {} {} {} --worker --mode={} --id={} -P{} > {} 2>&1"
        # )
        # cmds = cmds_template.format(
        #     strace_file_name,
        #     conf.get(section_name, "gramine_path"),
        #     conf.get(section_name, "gramine_manifest_path"),
        #     "ratls" if conf.is_sgx_enabled else "tls",
        #     id,
        #     conf.get("coordinator", "worker_manager_port"),
        #     temp_file_name,
        # ).split()

        # """Valgrind Debug"""
        # cmds = (
        #     (
        #         r"PYTHONHOME=~/sgx/lib/cpython-3.9.13-install "
        #         + r"PYTHONPATH=~/sgx/seccask2/pysrc:~/scvenv-autolearn/lib/python3.9/site-packages "
        #         + r"APP_HOME=/home/mlcask/sgx/seccask2 "
        #         + r"PYTHONMALLOC=malloc valgrind --tool=memcheck --leak-check=full "
        #         + r"--suppressions=/home/mlcask/sgx/lib/cpython-3.9.13/Misc/valgrind-python.supp "
        #         + r"{} --worker --mode={} --id={} -P{} > {} 2>&1"
        #     )
        #     .format(
        #         "/home/mlcask/sgx/seccask2/build/bin/seccask",
        #         "ratls"
        #         if conf.is_sgx_enabled and conf.getboolean("ratls", "enable")
        #         else "tls",
        #         id,
        #         conf.get("coordinator", "worker_manager_port"),
        #         temp_file_name,
        #     )
        #     .split()
        # )

        # cmds = r"SECCASK_DEBUG_ENCFS=1 PYTHONHOME=~/sgx/lib/cpython-3.9.5-install {} {} --worker --mode={} --id={} -P{} > {} 2>&1".format(
        cmds = r"{}{}PYTHONHOME=~/sgx/lib/cpython-3.9.13-install {} {} --worker --mode={} --id={} -P{} > {} 2>&1".format(
            "SECCASK_DEBUG_ENCFS=1 " if conf.getboolean("log", "log_encfs") else "",
            "SECCASK_PROFILE_IO=1 " if conf.getboolean("log", "log_io") else "",
            conf.get(section_name, "gramine_path"),
            conf.get(section_name, "gramine_manifest_path"),
            "ratls"
            if conf.is_sgx_enabled and conf.getboolean("ratls", "enable")
            else "tls",
            id,
            conf.get("coordinator", "worker_manager_port"),
            temp_file_name,
        ).split()

        if conf.getboolean("scheduler", "__debug_worker_creation_dry_run") is True:
            self.logger.warn(" ".join(cmds))
            self.logger.warn(
                "Dry run enabled. Please manually exec the above command. "
                "To disable, set schedule.__debug_worker_creation_dry_run to false"
            )
        else:
            self.logger.debug(f"CLI CMD: {' '.join(cmds)}")
            self.sshclient.exec_command("PYTHONUNBUFFERED=1 " + " ".join(cmds))

    def cache_worker(self, worker: "wc.BaseWorkerConnection"):
        self._active_workers.remove(worker)
        self._cached_workers.add(worker)

    def activate_worker(self, worker: "wc.BaseWorkerConnection"):
        self._cached_workers.remove(worker)
        self._active_workers.add(worker)

    @property
    def is_worker_set_full(self):
        return len(self._active_workers) + len(self._cached_workers) >= self._num_slot

    def get_compatible_worker_sync(
        self, component: p.Component, callback: Callable[[str], None],
    ) -> None:
        self.logger.debug(f"Component {component} getting compatible worker")
        for w in self._cached_workers:
            if conf.getboolean("scheduler", "__debug_singleton_worker"):
                """Always reuse worker"""
                self.logger.debug(f"Found Worker {w} for Component {component}")
                self.activate_worker(w)
                self._record_last_executed_component(w, component)

                self._print_workers()
                callback(w.id)
                return

            if conf.getboolean("scheduler", "enable_compatibility_check_on_caching"):
                if self.is_compatible(w, component):
                    self.logger.debug(f"Found Worker {w} for Component {component}")
                    self.activate_worker(w)
                    self._record_last_executed_component(w, component)
                    # notify(self._is_pool_updated)

                    self._print_workers()
                    callback(w.id)

                    return
                else:
                    self.logger.debug(
                        f"Worker {w} not compatible with Component {component}"
                    )
            else:
                self.logger.debug(f"Worker-component compatible check disabled")

        if len(self._active_workers) >= self._num_slot:
            raise WorkerPoolFull

        if self.is_worker_set_full:
            w = self._cached_workers.remove_end(component)
            # notify(self._is_pool_updated)

            self.logger.debug(
                f"Worker set full. Remove cached worker {w} based on policy"
            )

            cpp_coordinator.on_cache_full(w.id)

        self._execute_new_worker_command()

        self._waiting_components.add(component)
        self.logger.debug(f"Component {component} waiting for new worker")
        print(f"[Coordinator] TIME OF WAITING NEW WORKER: {time.time()}")

    def is_compatible(
        self, worker: "wc.BaseWorkerConnection", component: p.Component
    ) -> bool:
        if not worker.manifest:
            return False

        component_manifest = component.get_manifest()
        self.logger.debug(f"Worker manifest:")
        print(yaml.safe_dump(dict(worker.manifest)))
        self.logger.debug(
            f"Component manifest for [{component_manifest.name} {component_manifest.version}]:"
        )
        print(yaml.safe_dump(dict(component_manifest)))

        # Level 1: Library Version Compatibility
        if (
            worker.manifest.name == component_manifest.name
            and worker.manifest.version == component_manifest.version
        ):
            self.logger.debug(f"Worker {worker} == L1 == Component {component}")
            return True

        self.logger.debug(f"Worker {worker} == L1 X == Component {component}")

        # Level 2: Package Hash
        if worker.manifest.packages_hash == component_manifest.packages_hash:
            self.logger.debug(f"Worker {worker} == L2 == Component {component}")
            return True

        self.logger.debug(f"Worker {worker} == L2 X == Component {component}")

        if conf.getboolean("scheduler", "__debug_disable_level3_check"):
            return False
        # Level 3: Package Version Compatibility
        active_packages = worker.manifest.packages
        for p, v in component_manifest.packages.items():
            if p not in active_packages or v != active_packages[p]:
                self.logger.debug(f"Worker {worker} == L3 X == Component {component}")
                return False
        self.logger.debug(f"Worker {worker} == L3 == Component {component}")
        return True

    def on_worker_ready(
        self, worker: "wc.BaseWorkerConnection", callback: Callable[[p.Component], None]
    ):
        self._cached_workers.add(worker)
        # notify(self._is_pool_updated)

        for wc in self._waiting_components:
            if conf.getboolean("scheduler", "enable_compatibility_check_on_new_worker"):
                if not self.is_compatible(worker, wc):
                    self.logger.debug(
                        f"Worker {worker} not compatible with Component {wc}"
                    )
                    continue

            self.logger.debug(f"Found Worker {worker} for Component {wc}")
            self._waiting_components.remove(wc)

            if worker in self._new_workers:
                self._new_workers.remove(worker)
            self.activate_worker(worker)
            self._record_last_executed_component(worker, wc)
            # notify(self._is_pool_updated)

            callback(wc)
            break

        self._print_workers()

    def _record_last_executed_component(
        self, worker: "wc.BaseWorkerConnection", component: p.Component
    ):
        if worker.manifest:
            cm = component.get_manifest()
            worker.manifest.name = str(cm.name)
            worker.manifest.version = SemanticVersion.from_version_str(
                cm.version.version_str
            )
            self.logger.debug(f"{worker}'s last executed component is now: {component}")
            self.logger.debug(
                f"{worker.manifest.name}:{worker.manifest.version.version_str}"
            )

    async def close(self):
        """Close scheduler. This will trigger `ConnectionClose` to all workers."""
        for w in self._cached_workers:
            self.logger.debug(f"Sending exit to [{w}]")
            await w.exit()
        for w in self._active_workers:
            self.logger.debug(f"Sending exit to [{w}]")
            await w.exit()
