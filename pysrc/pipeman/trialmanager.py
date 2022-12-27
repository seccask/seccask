import os
import pickle
import pprint
import uuid
import time
from typing import Dict, List, Tuple

import colorama

from pipeman import storage
from pipeman.datasetmanager import DatasetManager
from pipeman.env import env
from pipeman.file import FileUtils
from pipeman.librarymanager import LibraryManager
from pipeman.meta import MetaKey, WorkspaceMeta
from pipeman.store import store
from pipeman.TrialTree import TreeNode, TrialTree
from pipeman.utils import LogUtils, PrintUtils, first
from pipeman.version import SemanticVersion

import cpp_coordinator


class TrialManager:
    def __init__(self):
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self._meta_storage = storage.MetaStorage(store)
        self._params_storage = storage.WorkspaceRuntimeFileStorage("params", store)
        self._output_storage = storage.WorkspaceRuntimeFileStorage("output", store)

        self.retrain = False

    def merge_workspace_branches(
        self, merge_branch_key: MetaKey, base_branch_key: MetaKey, depth: int
    ):
        merge_head_workspace_list = [
            WorkspaceMeta(self._meta_storage.get_branch_head(merge_branch_key))
        ]
        base_head_workspace_list = [
            WorkspaceMeta(self._meta_storage.get_branch_head(base_branch_key))
        ]

        merge_head_workspace_list.extend(
            [
                WorkspaceMeta(config)
                for config in self._meta_storage.get_lineage(merge_branch_key)
            ]
        )
        base_head_workspace_list.extend(
            [
                WorkspaceMeta(config)
                for config in self._meta_storage.get_lineage(base_branch_key)
            ]
        )

        print("Merge HEAD")
        pprint.pprint(merge_head_workspace_list)
        print("HEAD")
        pprint.pprint(base_head_workspace_list)

        workspace_list: List[WorkspaceMeta] = []
        workspace_list.extend(merge_head_workspace_list)
        workspace_list.extend(base_head_workspace_list)

        # TODO
        for workspace in workspace_list:
            workspace.outputs = {}
            workspace.params = {}
        #

        trial_tree = TrialTree(workspace_list)
        trial_tree.dfs_train(trial_tree._tree.root, self._train_node_list)
        with open("tree.dump", "wb") as f:
            pickle.dump(trial_tree._tree, f)
        with open("heads.dump", "wb") as f:
            pickle.dump(workspace_list, f)

    def commit_workspace(self, workspace: WorkspaceMeta):
        try:
            previous_workspace_config = self._meta_storage.get_branch_head(
                workspace.key
            )

            previous_workspace = WorkspaceMeta(previous_workspace_config)
            proposed_sv = SemanticVersion(
                branch=workspace.version.branch,
                api_version=previous_workspace.version.api_version,
                inc_version=previous_workspace.version.inc_version + 1,
            )
            trial_tree = TrialTree([previous_workspace, workspace])
        except KeyError:
            proposed_sv = SemanticVersion(
                branch=workspace.version.branch, api_version=0, inc_version=0
            )
            trial_tree = TrialTree([workspace])

        # TODO: we skip the compatibility check for now

        options = self._prepare_env(workspace)

        def equal(node_list, pipeline):
            for node, component in zip(node_list, pipeline):
                if node.key == component:
                    continue
                else:
                    return False
            return True

        nodes: List[TreeNode] = first(
            trial_tree.candidate_node_lists,
            condition=lambda nl: equal(nl, workspace.pipeline),
            default=None,
        )

        candidate_ids = list(
            map(lambda _: str(uuid.uuid4()), range(len(workspace.pipeline)))
        )

        pipeline_version = f"{workspace.version.branch}@{proposed_sv.api_version}.{proposed_sv.inc_version}"
        # coordinator.emit_msg(
        #     Message(
        #         "ExpRunner",
        #         "pipeline",
        #         [
        #             workspace.name,
        #             pipeline_version,
        #             [
        #                 x.to_string(with_version=True)
        #                 for x in workspace.pipeline
        #             ],
        #             candidate_ids,
        #         ],
        #     )
        # )

        cpp_coordinator.on_new_pipeline(
            [x.to_string(with_version=True) for x in workspace.pipeline], candidate_ids,
        )

        self._train_node_list(nodes, options, candidate_ids)

        self.logger.debug("Node list trained")

        executed = {"params": {}, "output": {}}
        skipped = {"params": {}, "output": {}}
        for node in nodes:
            try:
                # small trick
                # if node.outputs stores a path: it has been runned in this execution
                if os.path.exists(node.output):
                    executed["output"][
                        node.key.to_string(with_version=True)
                    ] = node.output
                    executed["params"][
                        node.key.to_string(with_version=True)
                    ] = node.params
                # if node.outputs stores a hashed version: it has been trained previously and is not runned in this execution
                else:
                    skipped["output"][
                        node.key.to_string(with_version=True)
                    ] = node.output
                    skipped["params"][
                        node.key.to_string(with_version=True)
                    ] = node.params
            except Exception:
                continue

        hp_map, out_map = self._save_pipeline_state(
            ws_key=workspace.key,
            output_path_dict=executed["output"],
            lib_params_dict=executed["params"],
            temp_dir=options["temp_dir"],
        )

        hp_map.update(skipped["params"])
        out_map.update(skipped["output"])

        workspace.outputs = out_map
        workspace.params = hp_map
        workspace.version = proposed_sv
        workspace.created_timestamp = time.time()

        meta_file_path = os.path.join(
            env.temp_path, workspace.key.to_string(with_version=True)
        )
        self.logger.debug("Writing meta file to local temp storage...")
        FileUtils.write_local_config(workspace.icp, meta_file_path)
        self.logger.debug("Done. Putting meta file to file storage...")
        self._meta_storage.put(workspace.key, meta_file_path)
        self.logger.debug("Put meta file to file storage")
        self.logger.debug(f"Pipeline {pipeline_version} committed")

    @staticmethod
    def _prepare_env(workspace: WorkspaceMeta) -> dict:
        base_dir = workspace.get_path(WorkspaceMeta.META_PATHS_BASE)
        venv_dir = os.path.join(
            base_dir, workspace.get_path(WorkspaceMeta.META_PATHS_VENV)
        )
        temp_dir = os.path.join(
            base_dir, workspace.get_path(WorkspaceMeta.META_PATHS_TEMP)
        )
        output_dir = os.path.join(
            base_dir, workspace.get_path(WorkspaceMeta.META_PATHS_OUTPUT)
        )

        for path in [base_dir, venv_dir, temp_dir, output_dir]:
            if not os.path.exists(path):
                os.makedirs(path)

        options = {
            "base_dir": base_dir,
            "venv_dir": venv_dir,
            "temp_dir": temp_dir,
            "output_dir": output_dir,
        }
        return options

    def _save_pipeline_state(
        self,
        ws_key: storage.MetaKey,
        lib_params_dict: Dict[str, Dict[str, str]],
        output_path_dict: Dict[str, str],
        temp_dir: str,
    ) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
        """Save pipeline state to runtime storage.

        Args:
            ws_key (storage.MetaKey): key to current workspace
            lib_params_dict (Dict[str, Dict[str, str]]): hyper-parameters list for libraries in the pipeline
            output_path_dict (Dict[str, str]): base folder of outputs
            options (dict): workspace-level path options

        Returns:
            Tuple[Dict[str, Dict[str, str]], Dict[str, str]]: hyper_params_version_map, output_version_map
        """
        self.logger.info("Saving pipeline state...")

        states = (
            {
                "name": "library params",
                "value": lib_params_dict,
                "action": FileUtils.dump_params_to,
                "storage": self._params_storage,
                "result": {},
            },
            {
                "name": "output paths",
                "value": output_path_dict,
                "action": FileUtils.archive_local_folder,
                "storage": self._output_storage,
                "result": {},
            },
        )
        for s in states:
            self.logger.info(
                colorama.Fore.GREEN + f"{s['name']}:" + colorama.Style.RESET_ALL
            )
            self.logger.info(PrintUtils.format(s["value"]))

            for key_str, value in s["value"].items():
                key = storage.MetaKey.build_from_string(key_str, with_version=True)
                dump_path = os.path.join(temp_dir, key.to_string())
                s["action"](value, dump_path)
                s["result"][key.to_string(with_version=True)] = s["storage"].put(
                    ws_key=ws_key, cpn_key=key, local_path=dump_path
                )

            self.logger.info(
                colorama.Fore.GREEN
                + f"{s['name']} ver mapping:"
                + colorama.Style.RESET_ALL
            )
            self.logger.info(PrintUtils.format(s["result"]))

        self.logger.info("Saved pipeline state")
        return tuple(s["result"] for s in states)

    def _build_venvs(self, node_list: List[TreeNode], options: dict):
        cmd_list: List[str] = []
        wd_list: List[str] = []
        exec_nodes: List[TreeNode] = []
        exec_nodes_indices: List[int] = []

        is_first_component = True
        input_path = ""
        for i, node in enumerate(node_list):
            if is_first_component:
                if node.trained:
                    self.logger.info("{} is trained".format(node.key))
                    if not self.retrain:
                        self.logger.info("Skipping")
                        continue
                    elif node.key.component_type == storage.MetaKey.GENERIC_DATASET_KEY:
                        self.logger.info("Is dataset. Skipping")
                        continue
                    else:
                        self.logger.info("Still retrain due to policy")

                prev_node = node if i == 0 else node_list[i - 1]

                if prev_node.key.component_type == storage.MetaKey.GENERIC_DATASET_KEY:
                    base_dir = os.path.join(
                        options["venv_dir"], prev_node.key.to_string(with_version=True)
                    )

                    dsman = DatasetManager()

                    t0 = time.time()
                    dsman.get_archive(prev_node.key, base_dir)
                    ds_meta = dsman.get_meta(prev_node.key)
                    t1 = time.time()

                    # prev_node.storage_size = FileUtils.get_dir_compressed_size(base_dir)
                    prev_node.storage_time = t1 - t0
                    prev_node.execution_time = 0
                    # self.logger.info("{} sized:{}".format(base_dir, prev_node.storage_size))

                    if ds_meta.version.branch == "not-schema-hashable":
                        input_path = base_dir + "/"
                    else:
                        input_path = ",".join(
                            [os.path.join(base_dir, file) for file in ds_meta.files]
                        )

                elif (
                    prev_node.key.component_type == storage.MetaKey.GENERIC_LIBRARY_KEY
                ):
                    if os.path.exists(prev_node.output):
                        input_path = prev_node.output
                    else:
                        t0 = time.time()
                        local_path = self._output_storage.get(
                            ws_key=prev_node.ws_key,
                            cpn_key=prev_node.key,
                            hversion=prev_node.output,
                        )
                        t1 = time.time()

                        # prev_node.storage_size = FileUtils.get_file_compressed_size(local_path)
                        prev_node.storage_time = t1 - t0
                        # self.logger.info("{} sized:{}".format(local_path, prev_node.storage_size))

                        input_path = (
                            os.path.join(
                                options["output_dir"],
                                prev_node.key.to_string(with_version=True),
                            )
                            + "/"
                        )

                        FileUtils.extract_archive_to(
                            source_path=local_path, dest_path=input_path
                        )

                is_first_component = False

            # transfer lib
            libman = LibraryManager()

            lib_meta = libman.get_meta(node.key)
            lib_base_path = os.path.join(
                options["venv_dir"], node.key.to_string(with_version=True)
            )
            libman.get_archive(node.key, lib_base_path)

            # input path ready
            wd_list.append(lib_base_path)
            cmd = lib_meta.train_script

            # prepare output dir
            output_path = os.path.join(
                options["output_dir"], node.key.to_string(with_version=True)
            )
            if not os.path.exists(output_path):
                os.makedirs(output_path)

            """save the dir for state save
            NOTE: save only newly generated outputs
            """
            output_path += "/"
            node.output = output_path
            # output_path_dict[node.key.to_string(with_version=True)] = output_path

            """insert input/ output location as params
            NOTE: it should be supported by the library
            """
            lib_param = lib_meta.train_params
            # lib_param = library_params_dict[pipeline_cpn_key.to_string(with_version=True)]

            lib_param["--input"] = input_path
            lib_param["--output"] = output_path
            lib_param["--vis"] = env.temp_path
            node.params = lib_param

            for k, v in lib_param.items():
                cmd = cmd + " " + str(k) + " " + str(v)

            self.logger.info(
                colorama.Fore.GREEN
                + "Appending command queue:"
                + colorama.Style.RESET_ALL
                + "\n"
                + cmd
            )
            # execute command
            cmd_list.append(cmd)
            exec_nodes.append(node)
            exec_nodes_indices.append(i)

            # next input = current output
            input_path = output_path

        return cmd_list, wd_list, exec_nodes, exec_nodes_indices

    def _train_node_list(
        self, node_list: List[TreeNode], options: dict, candidate_ids: List[str],
    ):
        self.logger.info("Training: ")
        self.logger.info(PrintUtils.format(node_list))

        last_output_path = ""

        cmd_list, wd_list, exec_nodes, exec_nodes_indices = self._build_venvs(
            node_list, options
        )

        start_time = time.time()
        self.logger.info(
            colorama.Fore.MAGENTA
            + "Pipeline execution starts: {}".format(start_time)
            + colorama.Style.RESET_ALL
        )

        for cmd, wd, node, i in zip(cmd_list, wd_list, exec_nodes, exec_nodes_indices):
            # if i < 4:
            #     continue

            self.logger.debug(
                f"[Comp. No. {i}] Executing component {i} in the pipeline"
            )

            t0 = time.time()

            self.logger.info(
                colorama.Fore.GREEN
                + "Raw command:"
                + colorama.Style.RESET_ALL
                + "\n"
                + cmd
            )
            cmds = ["python"] + cmd.split()

            """ SecCask 2
                Call C++ code. This will block the current pipeline evolution 
                process until receiving result from worker
            """
            
            print(f"[Coordinator] TIME OF NEW COMPONENT IDENTIFIED: {time.time()}")
            
            io_time: float = -1
            
            component_key = cpp_coordinator.get_component_key()
            if component_key == "":
                io_time = cpp_coordinator.on_new_component([candidate_ids[i], wd, "NULL", *cmds])
            else:
                io_time = cpp_coordinator.on_new_component(
                    [candidate_ids[i], wd, component_key, *cmds]
                )

            self.logger.debug("Back to pipeline execution")

            t1 = time.time()
            node.execution_time = t1 - t0
            node.io_time = io_time

            self.logger.debug("Node execution time recorded")

            # node.storage_size = FileUtils.get_dir_compressed_size(
            #     node.params["--output"]
            # ) + FileUtils.get_dir_compressed_size(wd)
            # self.logger.info("{} sized:{}".format(node.params["--output"], node.storage_size))

        end_time = time.time()
        self.logger.info(
            colorama.Fore.MAGENTA
            + f"Pipeline execution ends: {end_time}"
            + colorama.Style.RESET_ALL
        )
        self.logger.info(
            colorama.Fore.MAGENTA
            + f"Pipeline duration: {end_time - start_time}"
            + colorama.Style.RESET_ALL
        )

        last_output_path = os.path.join(exec_nodes[-1].output, "final_results.txt")
        perf = 0.0
        with open(last_output_path) as f:
            perf = float(f.readline())
        node_list[-1].perf = perf

        for node in node_list:
            node.trained = True
            self.logger.info("NODE TIME STORAGE TIME  : {}".format(node.storage_time))
            self.logger.info("NODE TIME EXECUTION TIME: {}".format(node.execution_time))
            self.logger.info("NODE TIME IO TIME: {}".format(node.io_time))
            # self.logger.info("NODE STORAGE SIZE: {}".format(node.storage_size))

        return node_list


if __name__ == "__main__":
    pass
