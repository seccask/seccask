import configparser
import copy
import os
import pprint
import tempfile
import time
from typing import Dict, List, Optional, Set, Tuple

from pipeman.meta import MetaKey, SemanticVersion, WorkspaceMeta
from pipeman.utils import LogUtils

MetaList = List[WorkspaceMeta]
StageDict = Dict[int, Set[MetaKey]]
CompatibilitySet = Set[Tuple[MetaKey, MetaKey]]


ROOT_KEY = MetaKey("TrialTree", "root")


class TreeNode:
    def __init__(self, node_key: MetaKey, trained: bool = False):
        self.key = node_key
        self.ws_key: Optional[MetaKey] = None
        self.trained = trained
        self.children: Set[TreeNode] = set()
        self.pruned = False
        self.output: str = ""
        self.params = {}
        self.storage_size = 0
        self.storage_time = 0.0
        self.execution_time = 0.0
        self.io_time = 0.0
        self.perf = 0.0

    @property
    def key_str(self) -> str:
        return self.key.to_string(with_version=True) if not self.is_root else ""

    @property
    def is_root(self) -> bool:
        return self.key.component_type == "TrialTree"

    @property
    def name(self) -> str:
        return self.key_str

    @property
    def id(self) -> str:
        return self.key_str

    def __str__(self):
        return "{} {}".format(self.key_str, self.trained)

    def __repr__(self):
        return "{} {}".format(self.key_str, self.trained)


class Tree:
    def __init__(self):
        self._root = TreeNode(ROOT_KEY, True)

    @property
    def root(self):
        return self._root

    def get_nodes_at_level(self, level: int) -> List[TreeNode]:
        if level == 0:
            return [self._root]
        else:
            node_list = []
            for node in self.get_nodes_at_level(level - 1):
                node_list.extend(node.children)
            return node_list

    def add_nodes(self, stage_dict: StageDict, depth: int):
        for i in range(depth):
            key_set = stage_dict[i]
            parent_nodes = self.get_nodes_at_level(i)
            for node in parent_nodes:
                for key in key_set:
                    if key.component_type == MetaKey.GENERIC_DATASET_KEY:
                        node.children.add(TreeNode(node_key=key, trained=True))
                    else:
                        node.children.add(TreeNode(node_key=key, trained=False))


class TrialTree:
    def __init__(self, workspaces: List[WorkspaceMeta]):
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self.logger.info("Workspace List: size = {}".format(len(workspaces)))
        self.logger.info(pprint.pformat(workspaces))

        self._stage_dict, self._tree_depth = self._init_stage_dict(workspaces)
        self.logger.info("Stage Dict:")
        for i, stage_set in self._stage_dict.items():
            self.logger.info("Stage {} - Size {}".format(i, len(stage_set)))
        self.logger.info(pprint.pformat(self._stage_dict))

        self._comp_dict = self._init_compatibility_dict2(workspaces)
        self.logger.info("Compatibility:")
        self.logger.info(pprint.pformat(self._comp_dict))

        self._tree = Tree()
        self._tree.add_nodes(self._stage_dict, self._tree_depth)

        self._walking_node_list = []
        self._all_walked_node_list = []

        self.logger.info("DFS Pruning:")
        self._dfs_prune(self._tree.root)
        self.logger.info("Size = {}".format(len(self._all_walked_node_list)))
        self.logger.info(pprint.pformat(self._all_walked_node_list))

        self.logger.info("Marking Node Training Status:")
        for workspace in workspaces:
            trained = False
            try:
                outputs = workspace.outputs
                if len(outputs) != 0:
                    trained = True
            except Exception:
                pass
            if trained:
                self._mark_trained_routine(workspace)
        self._all_walked_node_list.clear()
        self._dfs_prune(self._tree.root)
        self.logger.info("Size = {}".format(len(self._all_walked_node_list)))
        self.logger.info(pprint.pformat(self._all_walked_node_list))

        self.tempdir_list = []

    @property
    def candidate_node_lists(self) -> List[TreeNode]:
        return self._all_walked_node_list

    def _init_stage_dict(
        self, workspaces: List[WorkspaceMeta]
    ) -> Tuple[StageDict, int]:
        stages: StageDict = {}
        depth = 0
        for workspace in workspaces:
            for i, com_key in enumerate(workspace.pipeline):
                if i in stages:
                    stages[i].add(com_key)
                else:
                    stages[i] = set()
                    stages[i].add(com_key)
                if i > depth:
                    depth = i
                # pprint.pprint(stages)
        return stages, depth + 1

    def _init_compatibility_dict(self, workspaces: List[WorkspaceMeta]):
        compatibility_set = set()
        for workspace in workspaces:
            prev_com_key = None
            current_com_key = None

            for current_com_key in workspace.pipeline:
                compatibility_set.add((prev_com_key, current_com_key))
                prev_com_key = current_com_key
                # pprint.pprint(compatibility_set)

        return compatibility_set

    def _init_compatibility_dict2(self, workspaces: List[WorkspaceMeta]):
        compatibility_set = set()
        pipeline_len = len(workspaces[0].pipeline)

        for i in range(pipeline_len - 1):
            current_stage = {}
            next_stage = {}

            for workspace in workspaces:
                current_stage_key = workspace.pipeline[i]
                next_stage_key = workspace.pipeline[i + 1]
                current_api = current_stage_key.component_version.api_version

                if current_api not in current_stage:
                    current_stage[current_api] = set()
                    next_stage[current_api] = set()
                current_stage[current_api].add(current_stage_key)
                next_stage[current_api].add(next_stage_key)

            for api_level, key_set1 in current_stage.items():
                key_set2 = next_stage[api_level]
                for key1 in key_set1:
                    for key2 in key_set2:
                        compatibility_set.add((key1, key2))

                """
                if prev_com_key is not None and current_com_key is not None:
                    if current_com_key.component_version.api_version != prev_com_key.component_version.api_version:
                        for key1 in current_stage:
                            for key2 in next_stage:
                                compatibility_set.add((key1, key2))
                        current_stage.clear()
                        next_stage.clear()
                    else:
                        current_stage.add(current_com_key)
                        next_stage.add(workspace.pipeline[i+1])
                prev_com_key = current_com_key
                """
        return compatibility_set

    def _mark_trained_routine(self, workspace: WorkspaceMeta):
        """
        """
        pipeline = workspace.pipeline
        p_node = self._tree.root
        for component_key in pipeline:
            node_set = p_node.children
            for node in node_set:
                if component_key != node.key:
                    continue

                if node.key.component_type == MetaKey.GENERIC_LIBRARY_KEY:
                    node.output = workspace.outputs[
                        node.key.to_string(with_version=True)
                    ]
                    node.params = workspace.params[
                        node.key.to_string(with_version=True)
                    ]
                node.trained = True
                node.ws_key = workspace.key
                p_node = node

                break

    def _dfs_prune(self, node: TreeNode):
        if node.children:
            for child in node.children:
                # parent_key = copy.deepcopy(node.key)
                # child_key = copy.deepcopy(child.key)
                if (node.key, child.key) not in self._comp_dict and not node.is_root:
                    child.pruned = True
                else:
                    self._walking_node_list.append(child)
                    self._dfs_prune(child)
                    self._walking_node_list.pop()
        else:
            # pprint.pprint(self._walking_node_list)
            self._all_walked_node_list.append(copy.deepcopy(self._walking_node_list))

    def dfs_train(self, node: TreeNode, train_node_list_function):
        if node.children:
            for child in node.children:
                self._walking_node_list.append(child)
                if not child.pruned:
                    self.dfs_train(child, train_node_list_function)
                self._walking_node_list.pop()
        else:
            # pprint.pprint(self._walking_node_list)
            base_dir = tempfile.mkdtemp(prefix="seccask")
            train_node_list_function(
                self._walking_node_list, self._generate_options(base_dir)
            )
            # will be cleaned later
            self.tempdir_list.append(base_dir)
            self._all_walked_node_list.append(copy.deepcopy(self._walking_node_list))

    def _generate_options(self, base_dir: str) -> dict:
        venv_dir = os.path.join(base_dir, "venv/")
        temp_dir = os.path.join(base_dir, "temp/")
        output_dir = os.path.join(base_dir, "output/")

        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        if not os.path.exists(venv_dir):
            os.makedirs(venv_dir)
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        options = dict()
        options["base_dir"] = base_dir
        options["venv_dir"] = venv_dir
        options["temp_dir"] = temp_dir
        options["output_dir"] = output_dir

        return options


if __name__ == "__main__":

    def generate_workspace_meta(
        name: str,
        branch: str,
        api_version: int,
        inc_version: int,
        dataset_dict: dict,
        path_dict: dict,
        options: dict,
        description: str,
        pipeline: list,
        outputs: dict,
        params: dict,
    ) -> WorkspaceMeta:
        meta = WorkspaceMeta(configparser.ConfigParser())
        meta.init_sections()
        meta.meta_type = WorkspaceMeta.META_TYPE
        meta.workspace_type = WorkspaceMeta.META_CONFIG_WORKSPACE_TYPE_PRODUCTION
        meta.name = name
        meta.datasets = dataset_dict
        meta.paths = path_dict
        meta.description = "{} {} {} {}".format(name, branch, api_version, inc_version)
        meta.created_timestamp = time.time()
        meta.pipeline = pipeline
        meta.version = SemanticVersion(branch, api_version, inc_version)
        if outputs:
            meta.outputs = outputs
        if params:
            meta.params = params
        return meta

    data = MetaKey("dataset", "data", SemanticVersion("A", 0, 0))
    lib1 = MetaKey("library", "feature", SemanticVersion("master", 0, 0))
    lib2 = MetaKey("library", "hmm", SemanticVersion("master", 0, 0))
    lib3 = MetaKey("library", "nn", SemanticVersion("master", 0, 0))

    meta_list = []

    for i in range(5):
        meta_list.append(
            generate_workspace_meta(
                name="readmission_workspace",
                branch="master",
                api_version=0,
                inc_version=i,
                dataset_dict={WorkspaceMeta.META_DATASETS_TRAIN: data},
                path_dict={},
                options={"opt": 10},
                description="description",
                pipeline=[data, lib1, lib2, lib3],
                outputs={
                    data.to_string(with_version=True): i,
                    lib1.to_string(with_version=True): i,
                    lib2.to_string(with_version=True): i,
                    lib3.to_string(with_version=True): i,
                },
                params={
                    data.to_string(with_version=True): i,
                    lib1.to_string(with_version=True): i,
                    lib2.to_string(with_version=True): i,
                    lib3.to_string(with_version=True): i,
                },
            )
        )
        if i == 0:
            lib1.component_version.inc_version += 1
            lib2.component_version.inc_version += 1
        elif i == 1:
            lib2.component_version.api_version += 1
            lib3.component_version.inc_version += 1
        elif i == 2:
            lib3.component_version.inc_version += 1
        elif i == 3:
            lib1.component_version.inc_version += 1
            lib3.component_version.inc_version += 1
        elif i == 4:
            lib1.component_version.inc_version += 1
            lib2.component_version.inc_version += 1
            lib3.component_version.inc_version += 1

    pprint.pprint(meta_list)
    trial_tree = TrialTree(meta_list)
    print(" ")
