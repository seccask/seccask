from configparser import ConfigParser
import copy
import pprint
from abc import ABCMeta, abstractmethod
from tempfile import NamedTemporaryFile
from typing import List

from pipeman.meta import MetaKey
from pipeman.store.base_storage import BaseStorage, TransferDType
from pipeman.version import SemanticVersion


class Storage:
    """
    Gemini storage abstraction layer
    """

    def __init__(self, physical_storage: BaseStorage):
        self._phy_storage = physical_storage


# StringStorage based on Storage
class StringStorage(Storage):
    def __init__(self, storage_name: str, physical_storage: BaseStorage):
        super().__init__(physical_storage)

        self._name = storage_name

    @property
    def phy_storage(self):
        return self._phy_storage

    @property
    def name(self):
        return self._name

    def get_branch_head(self, str_key: str, str_branch: str) -> str:
        """
        Returns:
            str: content at head of branch `str_branch` of key `str_key`

        Raises:
            KeyError: if key does not exist
        """
        ret, raw_string = self.phy_storage.get(
            key=str_key, branch=str_branch, dtype=TransferDType.STRING
        )
        if raw_string is None:
            raise KeyError(f"Key {str_key} does not exist")

        return raw_string

    def get_version(self, str_key: str, hashed_version: str) -> str:
        """
        Returns:
            str: content with key `str_key` and version `hashed_version`
            
        Raises:
            KeyError: if key does not exist
        """
        ret, raw_string = self.phy_storage.get(
            key=str_key, hversion=hashed_version, dtype=TransferDType.STRING
        )
        if raw_string is None:
            raise KeyError(f"Key {str_key} does not exist")

        return raw_string

    def put(self, str_key: str, str_branch: str, raw_string: str):
        ret = self.phy_storage.put(
            key=str_key, branch=str_branch, dtype=TransferDType.STRING, value=raw_string
        )
        return ret.values["Version"]

    def merge(self, str_key: str, head_branch: str, merge_branch: str, raw_string: str):
        ret = self.phy_storage.merge(
            key=str_key,
            head_branch=head_branch,
            merge_branch=merge_branch,
            dtype=TransferDType.STRING,
            value=raw_string,
        )
        return ret.values["Version"]

    def head(self, str_key: str, str_branch: str):
        return self.phy_storage.head(key=str_key, branch=str_branch).values

    def branch(
        self,
        str_key: str,
        str_new_branch: str,
        str_refer_branch: str,
        str_refer_version: str,
    ):
        ret = self.phy_storage.branch(
            key=str_key,
            new_branch=str_new_branch,
            based_on_branch=str_refer_branch,
            refer_version=str_refer_version,
        )
        return ret

    def get_list_of_branches(self, str_key: str):
        ret = self.phy_storage.list_branch(key=str_key)
        return ret.values

    def get_list_with_str_prefix(self, prefix: str = "") -> list:
        ret = self.phy_storage.list_key()
        key_list = ret.values
        ret_list = list()
        for item in key_list:
            if item.startswith(prefix):
                ret_list.append(item)

        return ret_list

    def get_parents_by_branch_head(self, str_key: str, str_branch: str) -> list:
        return self.phy_storage.meta(key=str_key, branch=str_branch).values

    def get_parents_by_version(self, str_key: str, str_version: str) -> list:
        return self.phy_storage.meta(key=str_key, version=str_version).values


# FileStorage based on Storage
class FileStorage(Storage):
    def __init__(self, storage_name: str, physical_storage: BaseStorage):
        super().__init__(physical_storage)

        self._name = storage_name

    @property
    def phy_storage(self):
        return self._phy_storage

    @property
    def name(self):
        return self._name

    def get_branch_head(self, str_key: str, str_branch: str) -> str:
        """
        Returns:
            str: file path at head of branch `str_branch` of key `str_key`
            
        Raises:
            KeyError: if key does not exist
        """
        cmd_ret, local_path = self.phy_storage.get(
            key=str_key, branch=str_branch, dtype=TransferDType.FILE
        )
        if local_path is None:
            raise KeyError(f"Key {str_key} does not exist")

        return local_path

    def get_version(self, str_key: str, hashed_version: str) -> str:
        """
        Returns:
            str: file path at head of branch `str_branch` of key `str_key`
            
        Raises:
            KeyError: if key does not exist
        """
        cmd_ret, local_path = self.phy_storage.get(
            key=str_key, hversion=hashed_version, dtype=TransferDType.FILE
        )        
        if local_path is None:
            raise KeyError(f"Key {str_key} does not exist")

        return local_path

    def put(self, str_key: str, str_branch: str, local_path):
        ret = self.phy_storage.put(
            key=str_key, branch=str_branch, dtype=TransferDType.FILE, value=local_path
        )
        return ret.values["Version"]

    def merge(self, str_key: str, head_branch: str, merge_branch: str, local_path: str):
        ret = self.phy_storage.merge(
            key=str_key,
            head_branch=head_branch,
            merge_branch=merge_branch,
            dtype=TransferDType.FILE,
            value=local_path,
        )
        return ret.values["Version"]

    def branch(
        self,
        str_key: str,
        str_new_branch: str,
        str_refer_branch: str,
        str_refer_version: str,
    ):
        ret = self.phy_storage.branch(
            key=str_key,
            new_branch=str_new_branch,
            based_on_branch=str_refer_branch,
            refer_version=str_refer_version,
        )
        return ret

    def head(self, str_key: str, str_branch: str):
        return self.phy_storage.head(key=str_key, branch=str_branch).values

    def get_list_of_branches(self, str_key: str):
        ret = self.phy_storage.list_branch(key=str_key)
        return ret.values

    def get_list_with_str_prefix(self, prefix: str = "") -> list:
        ret = self.phy_storage.list_key()
        key_list = ret.values
        ret_list = list()
        for item in key_list:
            if item.startswith(prefix):
                ret_list.append(item)

        return ret_list

    def remove(self, key: MetaKey):
        pass

    def get_parents_by_branch_head(self, str_key: str, str_branch: str) -> list:
        return self.phy_storage.meta(key=str_key, branch=str_branch).values

    def get_parents_by_version(self, str_key: str, str_version: str) -> list:
        return self.phy_storage.meta(key=str_key, version=str_version).values


"""
Higher Level
"""


class SemanticFileStorage:
    __metaclass__ = ABCMeta

    COL_VERSION = "VersionMapping"
    COL_ENTITY = "Entity"

    def __init__(self, key_prefix: str, physical_storage: BaseStorage):
        self._version_storage = StringStorage(
            storage_name=self.COL_VERSION, physical_storage=physical_storage
        )
        self._entity_storage = FileStorage(
            storage_name=self.COL_ENTITY, physical_storage=physical_storage
        )
        self._key_prefix = key_prefix

    def _form_version_key(self, key: MetaKey) -> str:
        """Generate keys in the format 
        {key_prefix}::VersionMapping::{key.type}::{key.name}::{key.sversion}.

        Args:
            key (MetaKey): key

        Returns:
            str: formatted key
        """
        return "{}::{}::{}".format(
            self._key_prefix, self.COL_VERSION, key.to_string(with_version=True)
        )

    def _form_entity_key(self, key: MetaKey) -> str:
        """Generate keys in the format 
        {key_prefix}::Entity::{key.type}::{key.name}.

        Args:
            key (MetaKey): key

        Returns:
            str: formatted key
        """
        return "{}::{}::{}".format(
            self._key_prefix, self.COL_ENTITY, key.to_string(with_version=False)
        )

    @abstractmethod
    def __parse_path(self, path) -> str:
        """NOTE: In the base class, this parse function do nothing except 
        return the path. However, in the derived class, this function could 
        be override.
        """
        return path

    def get_branch_head(self, key: MetaKey):
        path = self._entity_storage.get_branch_head(
            str_key=self._form_entity_key(key=key),
            str_branch=key.component_version.branch,
        )
        return self.__parse_path(path)

    def get_semantic_version(self, key: MetaKey) -> str:
        # Get hashed version first
        hashed_version = self._version_storage.get_branch_head(
            str_key=self._form_version_key(key=key),
            str_branch=key.component_version.branch,
        )
        if hashed_version is None:
            raise KeyError(f"cannot find branch head of key {key}")

        metakey = self._form_entity_key(key)
        meta_path = self._entity_storage.get_version(
            str_key=metakey, hashed_version=hashed_version
        )
        if meta_path is None:
            raise KeyError(
                f"get file with key {metakey} and version {hashed_version} failed"
            )
        return self.__parse_path(meta_path)

    def put(self, key: MetaKey, local_path):
        # put the config
        ret = self._entity_storage.put(
            str_key=self._form_entity_key(key),
            str_branch=key.component_version.branch,
            local_path=local_path,
        )
        hashed_version = ret
        # record the new hash version
        self._version_storage.put(
            str_key=self._form_version_key(key),
            str_branch=key.component_version.branch,
            raw_string=hashed_version,
        )

    def merge(
        self,
        head_key: MetaKey,
        merge_head_key: MetaKey,
        new_head_key: MetaKey,
        local_path: str,
    ):
        """
        merge MERGE_HEAD to HEAD

        ----MERGE_HEAD------
                            |
        ----HEAD----------NEW_HEAD--->

        parameters:
            head_key: ref to HEAD
            merge_head_key: ref to MERGE_HEAD
            new_head_key: ref to NEW_HEAD
            local_path: content of NEW_HEAD, the conflict is assumed to have been resolved        
        """

        assert head_key.component_name == new_head_key.component_name
        assert merge_head_key.component_name == new_head_key.component_name

        assert head_key.component_type == new_head_key.component_type
        assert merge_head_key.component_type == new_head_key.component_type

        ret = self._entity_storage.merge(
            str_key=self._form_entity_key(new_head_key),
            head_branch=head_key.component_version.branch,
            merge_branch=merge_head_key.component_version.branch,
            local_path=local_path,
        )

        hashed_version = ret

        self._version_storage.put(
            str_key=self._form_version_key(new_head_key),
            str_branch=new_head_key.component_version.branch,
            raw_string=hashed_version,
        )

    def branch_on_branch_head(self, key: MetaKey, new_branch: str):
        """
        To be deprecated
        """

        hashed_version = self._entity_storage.head(
            str_key=self._form_entity_key(key), str_branch=key.component_version.branch
        )

        self._entity_storage.branch(
            str_key=self._form_entity_key(key),
            str_new_branch=new_branch,
            str_refer_branch=key.component_version.branch,
            str_refer_version=None,
        )

        self._version_storage.put(
            str_key=self._form_version_key(key),
            str_branch=key.component_version.branch,
            raw_string=hashed_version,
        )

    def branch_on_semantic_version(self, key: MetaKey, new_branch: str):
        # Get hashed version first
        hashed_version = self._version_storage.get_branch_head(
            str_key=self._form_version_key(key=key),
            str_branch=key.component_version.branch,
        )
        if hashed_version is None:
            return None
        else:
            ret = self._entity_storage.branch(
                str_key=self._form_entity_key(key),
                str_new_branch=new_branch,
                str_refer_branch=None,
                str_refer_version=hashed_version,
            )
            """
            NOTE:
            override the branch name in key: MetaKey, so a new version mapping will be written
            """
            branched_key = copy.deepcopy(key)
            branched_key.component_version.branch = new_branch
            if ret.is_success:
                self._version_storage.put(
                    str_key=self._form_version_key(branched_key),
                    str_branch=key.component_version.default_branch,
                    raw_string=hashed_version,
                )

    def get_parents_of_branch_head(self, key: MetaKey) -> list:
        primary_storage = self._entity_storage
        return primary_storage.get_parents_by_branch_head(
            str_key=self._form_entity_key(key), str_branch=key.component_version.branch
        )

    def get_parents_of_semantic_version(self, key: MetaKey) -> list:
        # Get hashed version first
        hashed_version = self._version_storage.get_branch_head(
            str_key=self._form_version_key(key=key),
            str_branch=key.component_version.branch,
        )

        return self._entity_storage.get_parents_by_version(
            str_key=self._form_entity_key(key), str_version=hashed_version
        )

    def get_parent_entity_of_semantic_version(self, key: MetaKey):
        parent_hversion = self.get_parents_of_semantic_version(key)
        return self._entity_storage.get_version(
            str_key=self._form_entity_key(key), hashed_version=parent_hversion
        )

    def traverse_branch(self, key: MetaKey) -> list:
        root = False
        node = self.get_parents_of_branch_head(key)
        lineage = [node]
        local_paths = []

        while not root:
            node = lineage[-1]
            length = len(node)
            if length == 1:
                # normal case
                parent_node = self._entity_storage.get_parents_by_version(
                    str_key=self._form_entity_key(key), str_version=node[0]
                )
                if parent_node is None:
                    break
                else:
                    lineage.append(parent_node)
            else:
                # may be merge node
                raise NotImplementedError()

        for version in lineage:
            local_path = self._entity_storage.get_version(
                str_key=self._form_entity_key(key), hashed_version=version[0]
            )
            local_paths.append(local_path)

        return local_paths

    def get_list_of_branches(self, key: MetaKey) -> list:
        primary_storage = self._entity_storage
        return primary_storage.get_list_of_branches(
            str_key=self._form_entity_key(key=key)
        )

    def get_list_of_components(self) -> list:
        primary_storage = self._entity_storage
        search_prefix = "{}::{}::".format(self._key_prefix, primary_storage.name)
        print("search prefix:" + search_prefix)
        return primary_storage.get_list_with_str_prefix(search_prefix)

    def get_list_of_component_versions(self, key: MetaKey) -> list:
        primary_storage = self._version_storage
        search_prefix = "{}::{}::{}".format(
            self._key_prefix, primary_storage.name, key.to_string(with_version=False)
        )
        print("search prefix:" + search_prefix)
        return primary_storage.get_list_with_str_prefix(search_prefix)


class MetaStorage(SemanticFileStorage):
    def __init__(self, physical_storage: BaseStorage):
        super().__init__(key_prefix="MetaStorage", physical_storage=physical_storage)

    def __parse_path(self, local_path: str) -> ConfigParser:
        config = ConfigParser()
        config.read(local_path)
        return config

    def get_branch_head(self, key: MetaKey):
        ret = super().get_branch_head(key=key)
        return self.__parse_path(ret)

    def get_semantic_version(self, key: MetaKey):
        ret = super().get_semantic_version(key=key)
        return self.__parse_path(ret)

    def get_lineage(self, key: MetaKey) -> List[ConfigParser]:
        lineage = self.traverse_branch(key)
        return list(map(self.__parse_path, lineage))


class DatasetStorage(SemanticFileStorage):
    def __init__(self, physical_storage: BaseStorage):
        super().__init__(key_prefix="DatasetStorage", physical_storage=physical_storage)


class LibraryStorage(SemanticFileStorage):
    def __init__(self, physical_storage: BaseStorage):
        super().__init__(key_prefix="LibraryStorage", physical_storage=physical_storage)


"""
Classes for Workspace Storage
"""


class WorkspaceRuntimeFileStorage(FileStorage):
    PREFIX = "WorkspaceRuntime"

    def __init__(self, storage_name: str, physical_storage: BaseStorage):
        super().__init__(storage_name, physical_storage)

    def _form_key(self, workspace_key: MetaKey, component_key: MetaKey):
        return "{}::{}::{}::{}::{}::{}".format(
            self.PREFIX,
            self.name,
            workspace_key.component_type,
            workspace_key.component_name,
            component_key.component_type,
            component_key.component_name,
        )

    # NOTE:
    # the hashed version are stored in workspace runtime meta like:
    #
    # library::dice::{semantic_version} = {hashed_version}
    # library::rnn::{semantic_version} = {hashed_version}

    # The runtime meta is stored in WorkspaceRuntimeStorage.runtime_meta_storage
    # Therefore, this class should only works with Class WorkspaceRuntimeStorage

    def get(self, ws_key: MetaKey, cpn_key: MetaKey, hversion: str) -> str:
        return super().get_version(
            str_key=self._form_key(ws_key, cpn_key), hashed_version=hversion
        )

    def put(self, ws_key: MetaKey, cpn_key: MetaKey, local_path: str):
        return super().put(
            str_key=self._form_key(ws_key, cpn_key),
            str_branch=ws_key.component_version.branch,
            local_path=local_path,
        )


"""
class WorkspaceRuntimeStorage:
    def __init__(self, env: GEMINIEnv):
        self._runtime_meta_storage = SemanticFileStorage(env=env, key_prefix="WorkspaceStorage")
        self._runtime_components_storage = WorkspaceRuntimeFileStorage(env=env, storage_name="WorkspaceStorage")

    @property
    def runtime_meta_storage(self):
        return self._runtime_meta_storage

    @property
    def runtime_components_storage(self):
        return self._runtime_components_storage
"""


if __name__ == "__main__":
    from pipeman.store import store

    fileStore = SemanticFileStorage(key_prefix="prefix", physical_storage=store)

    with NamedTemporaryFile("w") as f:
        testKey = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("master", 0, 1),
        )
        f.write(testKey.to_string(True))
        f.flush()
        fileStore.put(key=testKey, local_path=f.name)

    with NamedTemporaryFile("w") as f:
        testKey = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("master", 0, 2),
        )
        f.write(testKey.to_string(True))
        f.flush()
        fileStore.put(key=testKey, local_path=f.name)

    fileStore.branch_on_branch_head(
        key=MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("master", 0, 2),
        ),
        new_branch="dev",
    )

    with NamedTemporaryFile("w") as f:
        testKey = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("dev", 0, 1),
        )
        f.write(testKey.to_string(True))
        f.flush()
        fileStore.put(key=testKey, local_path=f.name)

    with NamedTemporaryFile("w") as f:
        testKey = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("dev", 0, 2),
        )
        f.write(testKey.to_string(True))
        f.flush()
        fileStore.put(key=testKey, local_path=f.name)

    with NamedTemporaryFile("w") as f:
        testKey = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("master", 0, 3),
        )
        f.write(testKey.to_string(True))
        f.flush()
        fileStore.put(key=testKey, local_path=f.name)

    master_branch = fileStore.traverse_branch(
        key=MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("master", 0, 3),
        )
    )

    dev_branch = fileStore.traverse_branch(
        key=MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("dev", 0, 3),
        )
    )

    pprint.pprint(master_branch)
    pprint.pprint(dev_branch)

    with NamedTemporaryFile("w") as f:
        merge_head_key = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("dev", 0, 2),
        )
        head_key = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("master", 0, 3),
        )
        new_head_key = MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion("master", 0, 4),
        )
        f.write(testKey.to_string(True))
        f.flush()
        fileStore.merge(
            head_key=head_key,
            merge_head_key=merge_head_key,
            new_head_key=new_head_key,
            local_path=f.name,
        )

    f = fileStore.get_branch_head(
        key=MetaKey(
            component_type="workspace",
            component_name="pipeline",
            component_version=SemanticVersion.build_zero_version(),
        )
    )
    print(f)

    # a = str(uuid.uuid1())
    # print(a)
    # strStore.put(key=testKey, raw_string=a)
    # a = strStore.get_branch_latest(testKey)
    # print(a)
    # #strStore.put(key=testKey, raw_string="test")

    # fileStore = FileStorage(env=env, storage_name="TestStringStorageName")
    # testKey = MetaKey(component_type="library", component_name="rnn", component_version=SemanticVersion("master", 0, 1))
    # fileStore.put(key=testKey, local_path="./nodes/file-test-master")
    # a = fileStore.get_branch_latest(testKey)
    # print(a)

    # testKey = MetaKey(component_type="library", component_name="rnn", component_version=SemanticVersion("master", 1, 3))
    # semStorage = SemanticFileStorage(env=gemini_env, key_prefix="LibraryStorage")
    # semStorage.put(key=testKey, local_path="./1.conf")
    # a = semStorage.get(key=testKey)
    # print(a.sections())

    # dataset_key = MetaKey(component_type="dataset",
    #                       component_name="nuh-admission",
    #                       component_version=SemanticVersion("master", 0, 1))

    # dataset_storage = DatasetStorage(env=gemini_env)
    # dataset_storage.put(key=dataset_key, local_path="README.md")
    # a = dataset_storage.get(key=dataset_key)
    # print(a)

    # file_storage = FileStorage(env=gemini_env, storage_name="test-file-storage")
    # file_storage.put(str_key="test-str-key",str_branch="master",local_path="README.md")
    # a = file_storage.getlist(key=None)
    # for item in a:
    #    print(item)

    # string_storage = StringStorage(env=gemini_env, storage_name="test-string-storage")
    # for i in range(10):
    #     string_storage.put(str_key="test-key"+str(i), str_branch="master", raw_string=str(i))
    # a = string_storage.getlist(None)
    # for item in a:
    #     print(item)

    # workspace_key = MetaKey(component_type="workspace",
    #                         component_name="nuh-readmission",
    #                         component_version=SemanticVersion("master", 0, 1))

    # testKey = MetaKey(component_type="library",
    #                   component_name="rnn",
    #                   component_version=SemanticVersion("master", 0, 1))

    # workspace_runtime_storage = WorkspaceRuntimeStorage(env=gemini_env)
    # workspace_runtime_storage.runtime_meta_storage.put(key=workspace_key, local_path="./1.conf")
    # workspace_runtime_storage.runtime_components_storage.put(ws_key=workspace_key,
    #                                                          cpn_key=testKey,
    #                                                          local_path="./nodes/file-test-master")
