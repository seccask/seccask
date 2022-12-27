from typing import List

from pipeman.store.base_storage import TransferDType
from pipeman.store.ustorecli import UStoreCLI
from pipeman.store.ustoreconf import UStoreCLIConstant, UStoreConf
from pipeman.utils import JsonableObject


class Block(JsonableObject):
    def __init__(self, number: int) -> None:
        self._number = number
        self._keys = set()

    @property
    def block_no(self) -> int:
        return self._number

    @property
    def keys(self) -> List[str]:
        return sorted(self._keys)

    def add_key(self, key: str) -> None:
        self._keys.add(key)

    def discard_key(self, key: str) -> None:
        self._keys.discard(key)

    @property
    def __dict__(self):
        return {str(self.block_no): self.keys}


class Replica(JsonableObject):
    def __init__(self, index: int) -> None:
        self._index = index
        self._blocks = set()

    @property
    def replica_idx(self) -> int:
        return self._index

    @property
    def blocks(self) -> List[Block]:
        return sorted(self._blocks, key=lambda x: x.block_no)

    def add_block(self, block: Block) -> None:
        self._blocks.add(block)

    def discard_block(self, block: Block) -> None:
        self._blocks.discard(block)

    @property
    def __dict__(self):
        d = {}
        for b in self.blocks:
            d.update(vars(b))
        return {str(self.replica_idx): d}


class UnverifiedKeys(JsonableObject):
    def __init__(self) -> None:
        self._replicas = set()

    @property
    def replicas(self) -> List[Replica]:
        return sorted(self._replicas, key=lambda x: x.replica_idx)

    def add_replica(self, replica: Replica) -> None:
        self._replicas.add(replica)

    def discard_replica(self, replica: Replica) -> None:
        self._replicas.discard(replica)

    @property
    def __dict__(self):
        d = {}
        for b in self.replicas:
            d.update(vars(b))
        return d


class LedgeBaseConf(UStoreConf):
    OPT_VERIFY_JSON: str
    CMD_VERIFY_JSON: str

    def __init__(self):
        super().__init__("ledgebase.ini")


class LedgeBaseCLI(UStoreCLI):
    def __init__(self, config: LedgeBaseConf, constant: UStoreCLIConstant):
        self._cli_config = config
        self._cli_constant = constant
        self.is_connected = False

    def get(
        self,
        key: str,
        branch: str = None,
        hversion: str = None,
        dtype: TransferDType = ...,
    ):
        return super().get(key, branch=branch, hversion=hversion, dtype=dtype)

    def verify(self, unverified_keys: UnverifiedKeys):
        cmd = self._get_verify_cmd(unverified_keys)

        cmd_ret = self._exec_command(cmd, None)
        return cmd_ret

    def _get_verify_cmd(self, unverified_keys: UnverifiedKeys):
        parameters = {
            self._cli_config.OPT_VERIFY_JSON: f"'{unverified_keys.to_json()}'"
        }
        return self._format_command(self._cli_config.CMD_VERIFY_JSON, parameters)
