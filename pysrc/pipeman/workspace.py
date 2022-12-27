import configparser
import os
import time

from pipeman import storage
from pipeman.env import env
from pipeman.file import FileUtils
from pipeman.meta import WorkspaceMeta
from pipeman.store import store
from pipeman.utils import LogUtils
from pipeman.version import SemanticVersion


class WorkspaceManager:
    def __init__(self):
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self._meta_storage = storage.MetaStorage(store)
        self._params_storage = storage.WorkspaceRuntimeFileStorage("params", store)
        self._output_storage = storage.WorkspaceRuntimeFileStorage("output", store)

    @property
    def meta_storage(self):
        return self._meta_storage

    @property
    def params_storage(self):
        return self._params_storage

    @property
    def output_storage(self):
        return self._output_storage

    def create(
        self,
        name,
        branch,
        dataset_dict: dict,
        path_dict: dict,
        options: dict,
        description: str,
        pipeline: list,
    ):
        meta = WorkspaceMeta(configparser.ConfigParser())
        meta.init_sections()
        meta.meta_type = WorkspaceMeta.META_TYPE
        meta.workspace_type = WorkspaceMeta.META_CONFIG_WORKSPACE_TYPE_PRODUCTION
        meta.name = name
        meta.datasets = dataset_dict
        # meta.solution = sln_key
        meta.paths = path_dict
        meta.description = description
        meta.created_timestamp = time.time()

        meta.pipeline = pipeline

        ws_key = storage.MetaKey(
            component_type=storage.MetaKey.GENERIC_WORKSPACE_KEY,
            component_name=name,
            component_version=SemanticVersion(
                branch=branch, api_version=0, inc_version=0
            ),
        )
        existing_meta_config = self.meta_storage.get_branch_head(key=ws_key)

        if existing_meta_config is None:
            meta.version = ws_key.component_version
            self.logger.debug(meta.version)
        else:
            existing_version = WorkspaceMeta(existing_meta_config).version
            ws_key.component_version.inc_version = existing_version.inc_version + 1
            meta.version = ws_key.component_version
            self.logger.debug(meta.version)

        tmp_file_path = os.path.join(
            env.temp_path, ws_key.to_string(with_version=False)
        )
        FileUtils.write_local_config(meta.icp, tmp_file_path)
        self.meta_storage.put(key=ws_key, local_path=tmp_file_path)

    def list_branches(self, workspace_name: str):
        key = storage.MetaKey.build_generic_workspace_key(
            workspace_name, SemanticVersion.build_zero_version()
        )
        return self.meta_storage.get_list_of_branches(key)

    def get(self, key: storage.MetaKey) -> WorkspaceMeta:
        branch_head_meta = self.meta_storage.get_branch_head(key=key)
        if branch_head_meta is None:
            raise RuntimeError("Did not receive a valid branch head meta")
        return WorkspaceMeta(branch_head_meta)

    def branch_on_branch_head(self, key: storage.MetaKey, new_branch: str):
        self.meta_storage.branch_on_branch_head(key=key, new_branch=new_branch)

    def branch_on_semantic_version(self, key: storage.MetaKey, new_branch: str):
        self.meta_storage.branch_on_semantic_version(key=key, new_branch=new_branch)


if __name__ == "__main__":
    pass
