"""
Library (Preprocess/Model) management
"""
import os
import time

from pipeman import storage
from pipeman.env import env
from pipeman.file import FileUtils
from pipeman.meta import LibraryMeta
from pipeman.store import store
from pipeman.utils import LogUtils
from pipeman.version import SemanticVersion


class LibraryManager:
    MANIFEST_PATH = ".manifest"

    def __init__(self):
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self._meta_storage = storage.MetaStorage(store)
        self._library_storage = storage.LibraryStorage(store)

    @property
    def meta_storage(self):
        return self._meta_storage

    @property
    def library_storage(self):
        return self._library_storage

    def create(self, source_path: str, working_branch: str):
        source_manifest_path = os.path.join(source_path, self.MANIFEST_PATH)
        self.logger.info(source_manifest_path)

        # checking manifest file
        manifest_meta = LibraryMeta(FileUtils.open_local_config(source_manifest_path))
        # working_branch = manifest_meta.version.branch

        if manifest_meta is None:
            self.logger.error("error opening manifest file " + source_path)
            raise FileNotFoundError("Manifest path: " + source_path)

        library_key = storage.MetaKey(
            component_type=storage.MetaKey.GENERIC_LIBRARY_KEY,
            component_name=manifest_meta.name,
            component_version=SemanticVersion(
                branch=working_branch, api_version=0, inc_version=0
            ),
        )

        try:
            # check current branch head
            library_meta_config = self.meta_storage.get_branch_head(key=library_key)
            # build meta using return configparser class
            library_meta = LibraryMeta(library_meta_config)
            # initial commit of the library
            self.logger.info(
                "previous version found, commit on default branch = master"
            )
            current_latest_sv = library_meta.version
            if manifest_meta.api_updated:
                proposed_api_version = current_latest_sv.api_version + 1
                proposed_inc_version = 0
            else:
                proposed_api_version = current_latest_sv.api_version
                proposed_inc_version = current_latest_sv.inc_version + 1
            proposed_sv = SemanticVersion(
                branch=working_branch,
                api_version=proposed_api_version,
                inc_version=proposed_inc_version,
            )
        except KeyError:
            self.logger.info(
                "no previous version found, commit on default branch = master with version 0.0"
            )
            proposed_sv = SemanticVersion(
                branch=working_branch, api_version=0, inc_version=0
            )

        library_key.component_version = proposed_sv

        # because we are going to commit the meta file based on the manifest file,
        # we ignore the version written in the manifest file
        manifest_meta.version = proposed_sv
        manifest_meta.created_timestamp = time.time()
        FileUtils.write_local_config(manifest_meta.icp, source_manifest_path)

        self.logger.info("proposed version " + proposed_sv.version_str)
        self.logger.info("proposed key " + library_key.to_string(with_version=True))

        self.logger.info("proceed to commit archive...")
        # archive the library
        archive_file_path = os.path.join(
            env.temp_path, library_key.to_string(with_version=False)
        )
        FileUtils.archive_local_folder(
            source_folder=source_path, dest_archive=archive_file_path
        )
        self.logger.info("Library archived at " + archive_file_path)

        self.library_storage.put(library_key, archive_file_path)
        self.meta_storage.put(library_key, source_manifest_path)
        self.logger.info("Library committed")

        self.logger.info(f"Library {library_key.to_string(with_version=True)} created")

    def remove(self, key: storage.MetaKey):
        pass

    def branch_on_branch_head(self, key: storage.MetaKey, new_branch):
        """
        Raises:
            KeyError
        """
        self.logger.info("HEAD meta get")
        meta = self.meta_storage.get_branch_head(key)
        if meta is None:
            raise KeyError(f"no such meta key: f{key}")
        library_meta = LibraryMeta(meta)
        self.logger.info("sv = {}".format(library_meta.version.version_str))
        key.component_version = library_meta.version
        self.branch_on_semantic_version(key, new_branch)

        print("LibMan: branch_on_branch_head() finished")

    def branch_on_semantic_version(self, key: storage.MetaKey, new_branch):
        self.meta_storage.branch_on_semantic_version(key=key, new_branch=new_branch)
        self.library_storage.branch_on_semantic_version(key=key, new_branch=new_branch)

        print("LibMan: branch_on_semantic_version() finished")

    def list_of_branch(self, key: storage.MetaKey):
        return self.meta_storage.get_list_of_branches(key=key)

    def list_of_components(self):
        return self.meta_storage.get_list_of_components()

    def list_of_component_versions(self, key: storage.MetaKey):
        return self.meta_storage.get_list_of_component_versions(key)

    def show_stat(self, key: storage.MetaKey):
        pass

    def get_meta(self, key: storage.MetaKey) -> LibraryMeta:
        version = self.meta_storage.get_semantic_version(key=key)
        if version is None:
            raise KeyError(f"no such semantic version: f{key}")
        return LibraryMeta(version)

    def get_meta_on_branch_head(self, key: storage.MetaKey) -> LibraryMeta:
        head = self.meta_storage.get_branch_head(key=key)
        if head is None:
            raise KeyError(f"no such branch head: {key}")
        return LibraryMeta(head)

    def get_archive(self, key: storage.MetaKey, dest_path: str):
        temp_path = self.library_storage.get_semantic_version(key=key)
        FileUtils.extract_archive_to(source_path=temp_path, dest_path=dest_path)
