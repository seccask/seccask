from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Optional, Tuple

from pipeman.utils import LogUtils


class TransferDType(Enum):
    FILE = 0
    STRING = 1


class StorageReturn:
    def __init__(self) -> None:
        super().__init__()
        self.values = dict()


class BaseStorage(metaclass=ABCMeta):
    """Abstract class for all interfaces storage subsystems.

    The BaseStorage class should be inherited by all storage subsystems before
    using by storage module.
    """

    def __init__(self) -> None:
        super().__init__()
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def get(
        self,
        key: str,
        branch: str = None,
        hversion: str = None,
        dtype: TransferDType = TransferDType.STRING,
    ) -> Tuple[str, Optional[str]]:
        pass

    @abstractmethod
    def put(
        self, key: str, branch: str, dtype: TransferDType, value: str
    ) -> StorageReturn:
        pass

    @abstractmethod
    def list_key(self) -> StorageReturn:
        pass

    @abstractmethod
    def head(self, key: str, branch: str) -> StorageReturn:
        pass

    @abstractmethod
    def branch(
        self,
        key: str,
        new_branch: str,
        based_on_branch: str = None,
        refer_version: str = None,
    ) -> StorageReturn:
        pass

    @abstractmethod
    def list_branch(self, key: str) -> StorageReturn:
        pass

    @abstractmethod
    def meta(self, key: str, version: str = None, branch: str = None) -> StorageReturn:
        pass

    @abstractmethod
    def merge(
        self,
        key: str,
        head_branch: str,
        merge_branch: str,
        dtype: TransferDType,
        value: str,
    ) -> StorageReturn:
        pass
