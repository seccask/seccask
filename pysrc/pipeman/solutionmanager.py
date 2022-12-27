"""
Solution management
"""
import configparser
import os
import time

from pipeman import storage
from pipeman.env import env
from pipeman.file import FileUtils
from pipeman.meta import SolutionMeta
from pipeman.store import store
from pipeman.version import SemanticVersion


class SolutionManager:
    def __init__(self):
        self._meta_storage = storage.MetaStorage(store)

    @property
    def meta_storage(self):
        return self._meta_storage

    def create(self, solution_name: str, preprocess: list):
        solution_key = storage.MetaKey.build_generic_solution_key(
            name=solution_name, sv=SemanticVersion.build_zero_version()
        )
        config = configparser.ConfigParser()
        meta = SolutionMeta(config)
        meta.init_sections()
        meta.name = solution_name
        meta.preprocess = preprocess
        meta.created_timestamp = time.time()
        # meta.model = model
        temp_path = os.path.join(
            env.temp_path, solution_key.to_string(with_version=False)
        )
        FileUtils.write_local_config(meta.icp, temp_path)
        self.meta_storage.put(solution_key, temp_path)

    def get(self, solution_key: storage.MetaKey) -> SolutionMeta:
        config = self.meta_storage.get_branch_head(solution_key)
        if config is None:
            raise KeyError(f"no such solution: {solution_key}")
        return SolutionMeta(config)

    def remove(self, key: storage.MetaKey):
        pass

    def list_of_components(self):
        pass

    def list_of_component_versions(self, key: storage.MetaKey):
        pass

    def show_stat(self, key: storage.MetaKey):
        pass


if __name__ == "__main__":
    slnman = SolutionManager()
    model = storage.MetaKey.build_generic_library_key(
        "rnn", SemanticVersion.build_zero_version()
    )
    plist = []
    plist.append(
        storage.MetaKey.build_generic_library_key(
            "dice", SemanticVersion.build_zero_version()
        )
    )
    plist.append(
        storage.MetaKey.build_generic_library_key(
            "extractor", SemanticVersion.build_zero_version()
        )
    )
    slnman.create("nuh-adm", plist, model)

    slnmeta = slnman.get(
        storage.MetaKey.build_generic_solution_key(
            "nuh-adm", SemanticVersion.build_zero_version()
        )
    )
    print(slnmeta.name)
    print(slnmeta.model)
    print(slnmeta.preprocess)
