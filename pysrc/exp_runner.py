import configparser
import os
import sys
import time
import yaml
from typing import List, Optional

from pipeman.datasetmanager import DatasetManager
from pipeman.librarymanager import LibraryManager
from pipeman.meta import MetaKey, WorkspaceMeta
from pipeman.utils import LogUtils
from pipeman.version import SemanticVersion
from manifest import ComponentType
from profiler import mem_profiler


def generate_workspace_meta(
    name: str,
    branch: str,
    api_version: int,
    inc_version: int,
    dataset_dict: dict,
    path_dict: dict,
    pipeline: list,
    outputs: Optional[dict] = None,
    params: Optional[dict] = None,
) -> WorkspaceMeta:
    meta = WorkspaceMeta(configparser.ConfigParser())
    meta.init_sections()
    meta.meta_type = WorkspaceMeta.META_TYPE
    meta.workspace_type = WorkspaceMeta.META_CONFIG_WORKSPACE_TYPE_PRODUCTION
    meta.name = name
    meta.version = SemanticVersion(branch, api_version, inc_version)
    meta.datasets = dataset_dict
    meta.paths = path_dict
    meta.description = "{} {} {} {}".format(name, branch, api_version, inc_version)
    meta.created_timestamp = time.time()
    meta.pipeline = pipeline
    meta.outputs = outputs if outputs else {}
    meta.params = params if params else {}
    return meta


def make_pipeline_and_commit(
    on_branch: str,
    pipeline: List[dict],
    ver: List[List[int]],
    workspace_base: str,
    trialman,
):
    path_dict = dict()
    path_dict[WorkspaceMeta.META_PATHS_BASE] = workspace_base
    path_dict[WorkspaceMeta.META_PATHS_OUTPUT] = f"output/"
    path_dict[WorkspaceMeta.META_PATHS_TEMP] = f"temp/"
    path_dict[WorkspaceMeta.META_PATHS_VENV] = f"venv/"

    ds_dict = dict()
    pipeline_keys = []

    for i, component in enumerate(pipeline):
        if component["type"] == ComponentType.DATASET.value:
            metakey = MetaKey.build_from_string(
                "{}::{}::not-schema-hashable.{}.{}".format(
                    component["type"], component["name"], ver[i][0], ver[i][1]
                ),
                with_version=True,
            )
            ds_dict[WorkspaceMeta.META_DATASETS_TRAIN] = metakey
            pipeline_keys.append(metakey)
        else:
            metakey = MetaKey.build_from_string(
                "{}::{}::{}.{}.{}".format(
                    component["type"],
                    component["name"],
                    on_branch,
                    ver[i][0],
                    ver[i][1],
                ),
                with_version=True,
            )
            pipeline_keys.append(metakey)

    ws_key = MetaKey.build_generic_workspace_key(
        "workspace", SemanticVersion.build_zero_version()
    )

    proposed_workspace = generate_workspace_meta(
        name=ws_key.component_name,
        branch=on_branch,
        api_version=ws_key.component_version.api_version,
        inc_version=ws_key.component_version.inc_version,
        dataset_dict=ds_dict,
        path_dict=path_dict,
        pipeline=pipeline_keys,
    )

    trialman.commit_workspace(proposed_workspace)


def commit_libs(
    test_source_base: str,
    datasets: List[str],
    libraries: List[str],
    branches: List[str],
):
    dsman = DatasetManager()
    libman = LibraryManager()

    for d in datasets:
        dsman.create(os.path.join(test_source_base, d))
    for l in libraries:
        for b in branches:
            libman.create(os.path.join(test_source_base, l), b)


class ExpManifest:
    def __init__(self, path: str) -> None:
        self._path = path
        with open(path, "r") as f:
            conf = yaml.safe_load(f)
        self._config = conf

    @property
    def dict(self) -> dict:
        return self._config

    @property
    def path(self) -> str:
        return self._path


def start(manifest_path: str):
    conf = ExpManifest(manifest_path).dict

    logger = LogUtils.get_default_named_logger("ExpRunner")
    logger.info(f"Experiment [{conf['name']}] Begin")

    test_source_base = conf["env"]["test_source_base"]
    workspace_base = conf["env"]["workspace_base"]
    branches = conf["branches"] if "branches" in conf else ["master"]

    from pipeman.trialmanager import TrialManager

    trialman = TrialManager()

    for task in conf["tasks"]:
        if task["action"] == "commit_libs":
            commit_libs(test_source_base, conf["datasets"], conf["libraries"], branches)

        elif task["action"] == "create_pipeline":
            make_pipeline_and_commit(
                task["branch"] if "branch" in task else "master",
                conf["pipeline"],
                task["versions"],
                workspace_base,
                trialman,
            )

        elif task["action"] == "merge_branch":
            trialman.merge_workspace_branches(
                MetaKey(
                    MetaKey.GENERIC_WORKSPACE_KEY,
                    "workspace",
                    SemanticVersion(task["merging_branch"], 0, 0),
                ),
                MetaKey(
                    MetaKey.GENERIC_WORKSPACE_KEY,
                    "workspace",
                    SemanticVersion(task["base_branch"], 0, 0),
                ),
                0,
            )

        else:
            logger.error(f"No such task: {task['action']}")
            os._exit(1)

    logger.warn(f"Experiment {conf['name']} done!")

    import cpp_io_profiler

    io_time = cpp_io_profiler.get()
    if io_time > 0:
        print(f"IO SPENT: {io_time}")

    mem_profiler.profile()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} ExperimentManifestPath")
        sys.exit(1)

    start(sys.argv[1])
