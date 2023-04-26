import hashlib
import os
import time
from typing import List, Optional, Union

from pipeman.env import env
from pipeman.config import default_config as conf
from pipeman.store.base_storage import (
    BaseStorage,
    StorageReturn,
    TransferDType,
)

# Below module is created from pybind11 and thus have no source
import cpp_coordinator  # type: ignore


class FileSystemStorage(BaseStorage):
    """FileSystem storage subsystem.

    This is a storage subsystem purely using file system as its physical
    storage. It manipulates files to store components and some metadata, plus
    uses directory hierarchy to include metainfo (component name, branch, etc.)
    """

    CONFIG_SECTION = "storage_filesystem"
    PARENTS_FILE_NAME = "PARENTS"
    CHUNKSIZE = int(conf.get(CONFIG_SECTION, "chunk_size"))
    GENERIC_FILE_NAME = conf.get(CONFIG_SECTION, "generic_file_name")
    PREFIX = conf.get(CONFIG_SECTION, "prefix")

    def __init__(self, base_path: str = "SecCask") -> None:
        """Create a new file system storage

        Args:
            base_path (str): A path specifying where data get stored
        """
        super().__init__()
        self.base_path = os.path.join(self.PREFIX, base_path)

    def connect(self):
        self._check_or_create_dir(self.base_path)

    def _check_or_create_dir(self, abspath: str):
        if not os.path.exists(abspath):
            os.makedirs(abspath, exist_ok=True)

    def disconnect(self):
        """Do nothing"""
        pass

    def get(
        self,
        key: str,
        branch: str = None,
        hversion: str = None,
        dtype: TransferDType = TransferDType.STRING,
    ):
        start_time: Union[float, None] = None
        if conf.getboolean("log", "log_filesystem_storage"):
            start_time = time.time()

        file_path = self._get_file_path(key, branch, hversion)
        if file_path is None:
            if start_time is not None:
                self.logger.debug(
                    f"[TIME: {time.time() - start_time}] Get [{key}]::[{branch}] failed"
                )
            return None, None

        file_path = os.path.join(file_path, self.GENERIC_FILE_NAME)

        if dtype == TransferDType.FILE:
            # set a temporary file on remote server
            remote_file = "{}-{}-{}".format(key, branch, time.time())
            local_file = os.path.join(env.temp_path, remote_file)

            with open(file_path, "rb") as rf:
                with open(local_file, "wb") as wf:
                    while True:
                        chunk = rf.read(self.CHUNKSIZE)
                        if not chunk:
                            break

                        wf.write(chunk)

            if start_time is not None:
                self.logger.debug(
                    f"[TIME: {time.time() - start_time}] Get [{key}]::[{branch}] from dir: {file_path} to dir: {local_file}"
                )
            return None, local_file

        elif dtype == TransferDType.STRING:
            with open(file_path, "r") as f:
                content = f.read()

            if start_time is not None:
                self.logger.debug(
                    f"[TIME: {time.time() - start_time}] Get [{key}]::[{branch}] from dir: {file_path}"
                )
            return None, content

    def _get_file_path(
        self,
        key: str,
        branch: Optional[str] = None,
        hversion: Optional[str] = None,
    ) -> Optional[str]:
        result = None
        if hversion is not None:
            result = self._get_path_from_hashed_version(key, hversion)
        elif branch is not None:
            result = self._get_head_path_from_branch(key, branch)
        else:
            raise ValueError("Not specifying one of branch and hversion")
        return result

    def _get_path_from_branch(self, key: str, branch: str) -> str:
        return os.path.abspath(os.path.join(self.base_path, key, branch))

    def _get_head_path_from_branch(self, key: str, branch: str) -> Union[str, None]:
        head_version = self._get_head_version(key, branch)
        if head_version is None:
            return None
        else:
            return os.path.join(self._get_path_from_branch(key, branch), head_version)

    def _get_path_from_hashed_version(self, key: str, hversion: str) -> str:
        for branch in self.list_branch(key):
            if os.path.exists(os.path.join(self.base_path, key, branch, hversion)):
                return os.path.join(self._get_path_from_branch(key, branch), hversion)

        return ""

    def _get_head_version(self, key: str, branch: str) -> Union[str, None]:
        file_path = os.path.join(self._get_path_from_branch(key, branch), "@HEAD")
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r") as f:
            content = f.read()
        return content

    def _set_head_version(self, key: str, branch: str, hversion: str) -> None:
        with open(
            os.path.join(self._get_path_from_branch(key, branch), "@HEAD"), "w"
        ) as f:
            f.write(hversion)

    def put(self, key: str, branch: str, dtype: TransferDType, value: str):
        start_time: Union[float, None] = None
        if conf.getboolean("log", "log_filesystem_storage"):
            start_time = time.time()

        remote_dir = self._get_path_from_branch(key, branch)
        self._check_or_create_dir(remote_dir)
        remote_file_path = os.path.join(remote_dir, self.GENERIC_FILE_NAME)

        if dtype == TransferDType.FILE:
            """To be more efficient (read file only once), here we do copy and
            compute hashed version simultanenously
            """
            hash_generator = hashlib.sha256()
            hash_generator.update(f"{time.time()}##{key}::{branch}::".encode())

            local_file_path = value

            with open(local_file_path, "rb") as rf:
                with open(remote_file_path, "wb") as wf:
                    while True:
                        chunk = rf.read(self.CHUNKSIZE)
                        if not chunk:
                            break

                        hash_generator.update(chunk)
                        wf.write(chunk)

            hversion = hash_generator.hexdigest()

        elif dtype == TransferDType.STRING:
            with open(remote_file_path, "w") as f:
                f.write(value)

            # Compute non-collisional SHA256 as hashed version
            hversion = hashlib.sha256(
                f"{time.time()}##{key}::{branch}::{value}".encode()
            ).hexdigest()

        # Move file to correct directory (with hashed version)
        new_dir = os.path.join(os.path.dirname(remote_file_path), hversion)
        self._check_or_create_dir(new_dir)
        os.rename(remote_file_path, os.path.join(new_dir, self.GENERIC_FILE_NAME))

        # Move HASH file to destination (Enabled when EncFS is used)
        component_key = cpp_coordinator.get_component_key()
        if component_key != "":
            os.rename(
                f"{remote_file_path}.hash",
                os.path.join(new_dir, f"{self.GENERIC_FILE_NAME}.hash"),
            )

        # Write parents to PARENTS_FILE_NAME
        current_head = self._get_head_version(key, branch)
        with open(os.path.join(new_dir, self.PARENTS_FILE_NAME), "w") as f:
            if current_head is not None:
                f.write(current_head)
            else:
                f.write("<null>")

        # Shift branch HEAD
        self._set_head_version(key, branch, hversion)

        ret = StorageReturn()
        ret.values["Version"] = hversion

        if start_time is not None:
            self.logger.debug(
                f"[TIME: {time.time() - start_time}] Put [{key}]::[{branch}] to dir: {new_dir}"
            )

        return ret

    def list_key(self):
        return [f.path for f in os.scandir(self.base_path) if f.is_dir()]

    def head(self, key: str, branch: str):
        ret = StorageReturn()
        ret.values["Version"] = self._get_head_version(key, branch)
        return ret

    def branch(
        self,
        key: str,
        new_branch: str,
        based_on_branch: str = None,
        refer_version: str = None,
    ):
        raise NotImplementedError()

    def list_branch(self, key: str) -> List[str]:
        key_dir = os.path.abspath(os.path.join(self.base_path, key))
        return [f.path for f in os.scandir(key_dir) if f.is_dir()]

    def meta(self, key: str, version: str = None, branch: str = None):
        start_time: Union[float, None] = None
        if conf.getboolean("log", "log_filesystem_storage"):
            start_time = time.time()

        file_path = self._get_file_path(key, branch, version)
        if file_path is None:
            if start_time is not None:
                self.logger.debug(
                    f"[TIME: {time.time() - start_time}] Get [{key}]::[{branch}] failed"
                )
            return None, None

        file_path = os.path.join(file_path, self.PARENTS_FILE_NAME)

    def merge(
        self,
        key: str,
        head_branch: str,
        merge_branch: str,
        dtype: TransferDType,
        value: str,
    ):
        raise NotImplementedError()
