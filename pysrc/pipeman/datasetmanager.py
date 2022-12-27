"""
Dataset management
"""
import csv
import hashlib
import os
import time

from pipeman import storage
from pipeman.env import env
from pipeman.file import FileUtils
from pipeman.meta import DatasetMeta
from pipeman.store import store
from pipeman.utils import LogUtils
from pipeman.version import SemanticVersion


class DatasetManager:
    def __init__(self):
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self._meta_storage = storage.MetaStorage(store)
        self._dataset_storage = storage.DatasetStorage(store)

    @property
    def meta_storage(self):
        return self._meta_storage

    @property
    def dataset_storage(self):
        return self._dataset_storage

    def _cal_dataset_schema_hash(self, csv_files: list) -> str:
        headers = []
        for file_name in csv_files:
            with open(file_name, "r") as csv_file:
                csv_reader = csv.reader(csv_file)
                header = next(csv_reader, None)
            headers.extend(header)

        headers = [item.upper().replace(" ", "") for item in headers]
        headers.sort()
        schema = ";".join(headers).encode(encoding="utf-8")
        return str(hashlib.md5(schema).hexdigest())

    def create(self, source_path: str) -> storage.MetaKey:
        source_manifest_path = os.path.join(source_path, ".manifest")
        self.logger.info(source_manifest_path)

        # checking manifest file
        manifest_meta = DatasetMeta(FileUtils.open_local_config(source_manifest_path))
        source_base = os.path.dirname(source_manifest_path)
        file_list = []
        for file_name in manifest_meta.files:
            if file_name == "all":
                manifest_meta.schema_hash = "not-schema-hashable"
                manifest_meta.version.branch = manifest_meta.schema_hash
                break
            else:
                file_list.append(os.path.join(source_base, file_name))

        # refresh the schema md5
        if manifest_meta.schema_hash != "not-schema-hashable":
            manifest_meta.schema_hash = self._cal_dataset_schema_hash(file_list)

            manifest_meta.version.branch = manifest_meta.schema_hash

        if manifest_meta is None:
            self.logger.error("error opening manifest file " + source_path)
            raise FileNotFoundError("Manifest path: " + source_path)

        dataset_key = storage.MetaKey(
            component_type=storage.MetaKey.GENERIC_DATASET_KEY,
            component_name=manifest_meta.name,
            component_version=SemanticVersion(
                branch=manifest_meta.schema_hash, api_version=0, inc_version=0
            ),
        )

        try:
            # check current branch head
            dataset_meta_config = self.meta_storage.get_branch_head(key=dataset_key)
            # build meta using return configparser class
            dataset_meta = DatasetMeta(dataset_meta_config)
            # initial commit of the library
            self.logger.info(
                "previous version found, commit on default branch = master"
            )
            current_latest_sv = dataset_meta.version
            proposed_api_version = current_latest_sv.api_version
            proposed_inc_version = current_latest_sv.inc_version + 1
            proposed_sv = SemanticVersion(
                branch=manifest_meta.schema_hash,
                api_version=proposed_api_version,
                inc_version=proposed_inc_version,
            )
        except KeyError:
            self.logger.info(
                "no previous version found, commit on default branch = master with version 0.0"
            )
            proposed_sv = SemanticVersion(
                branch=manifest_meta.schema_hash, api_version=0, inc_version=0
            )

        dataset_key.component_version = proposed_sv

        # because we are going to commit the meta file based on the manifest file,
        # we ignore the version written in the manifest file
        manifest_meta.version = proposed_sv
        manifest_meta.created_timestamp = time.time()
        FileUtils.write_local_config(manifest_meta.icp, source_manifest_path)

        self.logger.info("proposed version " + proposed_sv.version_str)
        self.logger.info("proposed key " + dataset_key.to_string(with_version=True))

        self.logger.info("proceed to commit archive...")
        # archive the library
        archive_file_path = os.path.join(
            env.temp_path, dataset_key.to_string(with_version=False)
        )
        FileUtils.archive_local_folder(
            source_folder=source_path, dest_archive=archive_file_path, remove_base=True,
        )
        self.logger.info("dataset archived at " + archive_file_path)

        self.dataset_storage.put(dataset_key, archive_file_path)
        self.meta_storage.put(dataset_key, source_manifest_path)

        self.logger.info("Dataset committed")
        self.logger.info(f"Dataset {dataset_key.to_string(with_version=True)} created")
        
        return dataset_key

    def remove(self, key: storage.MetaKey):
        pass

    def branch_on_branch_head(self, key: storage.MetaKey, new_branch):
        """

        """
        self.logger.info("HEAD meta get")
        meta = self.meta_storage.get_branch_head(key)
        dataset_meta = DatasetMeta(meta)
        self.logger.info("sv = {}".format(dataset_meta.version.version_str))
        key.component_version = dataset_meta.version
        self.branch_on_semantic_version(key, new_branch)
        self.logger.info("LibMan: branch_on_branch_head() finished")

    def branch_on_semantic_version(self, key: storage.MetaKey, new_branch):
        """

        """
        self.meta_storage.branch_on_semantic_version(key=key, new_branch=new_branch)
        self.dataset_storage.branch_on_semantic_version(key=key, new_branch=new_branch)
        self.logger.info("LibMan: branch_on_semantic_version() finished")

    def list_of_branch(self, key: storage.MetaKey):
        return self.meta_storage.get_list_of_branches(key=key)

    def list_of_components(self):
        return self.meta_storage.get_list_of_components()

    def list_of_component_versions(self, key: storage.MetaKey):
        return self.meta_storage.get_list_of_component_versions(key)

    def show_stat(self, key: storage.MetaKey):
        pass

    def get_meta(self, key: storage.MetaKey) -> DatasetMeta:
        return DatasetMeta(self.meta_storage.get_semantic_version(key=key))

    def get_meta_on_branch_head(self, key: storage.MetaKey) -> DatasetMeta:
        return DatasetMeta(self.meta_storage.get_branch_head(key=key))

    def get_archive(self, key: storage.MetaKey, dest_path: str):
        temp_path = self.dataset_storage.get_semantic_version(key=key)
        FileUtils.extract_archive_to(source_path=temp_path, dest_path=dest_path)

