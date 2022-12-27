# UStore Connection Configuration File
# NOTE:
#   This configuration file should not contain any code
# TODO:
#   Initialize values from configuration files
import configparser
import os

from pipeman.env import env


class UStoreConf:
    USTORE_ADDR: str
    USTORE_USERNAME: str
    USTORE_KEY_PATH: str
    SSH_CLIENT_CMD_PREFIX: str
    USTORE_CMD_CLI: str
    MAX_RETRY_TIMES: str

    OPT_DATATYPE: str
    OPT_FILE: str
    OPT_KEY: str
    OPT_KEY_MAP_ENTRY: str
    OPT_DATA_VALUE: str
    OPT_REF_DATA_VALUE: str
    OPT_BRANCH: str
    OPT_REF_BRANCH: str
    OPT_VERSION: str
    OPT_REF_VERSION: str

    CMD_GET: str
    CMD_PUT: str
    CMD_BRANCH: str
    CMD_LIST_KEY: str
    CMD_META: str
    CMD_MERGE: str
    CMD_HEAD: str
    CMD_LATEST: str
    CMD_LIST_BRANCH: str

    _SECTION_DB_CONNECTION = "db-connection"
    _SECTION_CLI_OPTIONS = "cli-options"
    _SECTION_CLI_CMDS = "cli-commands"

    def __init__(self, filename="ustore_ncrs"):
        self._config_path = os.path.join(env.config_base, filename)
        self._config = configparser.ConfigParser()
        self._config.read(self._config_path)
        for section in self._config.sections():
            for k, v in self._config.items(section):
                self.__dict__.update({k.upper(): v})

    @property
    def sftp_temp_path(self) -> str:
        return env.temp_path


# noinspection PyPep8Naming
class UStoreCLIConstant:
    RET_SUCCESS = "SUCCESS"
    RET_ACTION_GET = "GET"
    RET_ACTION_PUT = "PUT"
    RET_ACTION_LIST_KEY = "LIST_KEY"
    RET_ACTION_HEAD = "HEAD"
    RET_ACTION_LATEST = "LATEST"
    RET_ACTION_BRANCH = "BRANCH"
    RET_ACTION_LIST_BRANCH = "LIST_BRANCH"
    RET_ACTION_META = "META"
    RET_ACTION_MERGE = "MERGE"
