import json
import logging
import os
import pwd
from configparser import ConfigParser
from pathlib import Path
from typing import Dict

__all__ = ["default_config"]


class Configuration:
    """Configuration Parser.

    This class contains common logic of parsing configuration files.

    All configration files are located in $APP_HOME/<CONFIG_FOLDER_PATH> folder.

    The main configuration file is `config.ini`.
    """

    CONFIG_FOLDER_PATH = ".conf"

    @classmethod
    def get_app_home(cls):
        """
        Retrieve environment variable APP_HOME with fallback $PWD
        """
        if "APP_HOME" not in os.environ:
            result = os.getcwd()
            logging.warning(
                "APP_HOME not defined. Use current working directory: %s" % result
            )
        else:
            result = os.environ["APP_HOME"]
            if not os.path.exists(result):
                raise Exception("APP_HOME is not a valid directory: %s" % result)
        return result

    def __init__(self, filename: str, defaults: Dict[str, Dict[str, str]]) -> None:
        self._filename = filename
        self._defaults = defaults
        self._app_home = self.get_app_home()
        self._config_path = os.path.join(
            self._app_home, self.CONFIG_FOLDER_PATH, filename
        )
        self._parser = ConfigParser()
        self._parser.read(self._config_path)
        self._escape_dict = {
            "$HOME": str(Path.home()),
            "$USER": pwd.getpwuid(os.getuid()).pw_name,
        }
        self._parser.set(
            "env", "is_sgx_enabled", "true" if self.is_sgx_enabled else "false"
        )

    @property
    def is_sgx_enabled(self):
        return os.getenv("SGX") is not None

    def _check_key_existence(self, section: str, key: str) -> None:
        if section not in self._defaults or key not in self._defaults[section]:
            raise KeyError(f"{section}.{key} not found in config file {self._filename}")

    def get(self, section: str, key: str) -> str:
        self._check_key_existence(section, key)

        raw_value = self._parser.get(
            section, key, fallback=self._defaults[section][key]
        )
        for k, v in self._escape_dict.items():
            raw_value = raw_value.replace(k, v)
        return raw_value

    def getboolean(self, section: str, key: str) -> bool:
        self._check_key_existence(section, key)

        raw_value = self._parser.getboolean(
            section, key, fallback=bool(self._defaults[section][key])
        )
        return raw_value

    def getint(self, section: str, key: str) -> int:
        self._check_key_existence(section, key)

        raw_value = self._parser.getint(
            section, key, fallback=int(self._defaults[section][key])
        )
        return raw_value

    def __str__(self):
        result = {}

        for section, section_dict in self._defaults.items():
            result[section] = {}
            for k in section_dict.keys():
                result[section][k] = self.get(section, k)

        return json.dumps(result, sort_keys=False, indent=4)


DEFUALTS_CONFIG_INI = {
    "env": {
        "temp_path": "$HOME/gemini-pipeline/gemini-pipeline/temp",
        "is_sgx_enabled": "false",
    },
    "coordinator": {
        "host": "127.0.0.1",
        "worker_manager_port": "50200",
        "webapi_port": "5020",
    },
    "storage": {"storage_engine": "forkbase"},
    "storage_ledgebase": {
        "base_path": "/nfs/host/sgx/seccask/framework/lib/ustore_release",
    },
    "storage_filesystem": {
        "chunk_size": "65536",
        "generic_file_name": "VALUE",
        "prefix": "$HOME/fsstore",
    },
    "storage_rdbms": {
        "user": "$USER",
        "ssl_cert_path": "$HOME/cert.pem",
        "ssl_key_path": "$HOME/key.pem",
    },
    "scheduler": {
        "default_num_slot": "4",
        "enable_compatibility_check_on_caching": "true",
        "enable_compatibility_check_on_new_worker": "false",
        "__debug_disable_level3_check": "false",
        "__debug_worker_creation_dry_run": "false",
        "__debug_singleton_worker": "false",
    },
    "worker": {
        "gramine_path": "/usr/local/bin/gramine-direct",
        "gramine_manifest_path": "$HOME/gramine-manifest/python",
    },
    "worker_sgx": {
        "gramine_path": "/usr/local/bin/gramine-sgx",
        "gramine_manifest_path": "$HOME/gramine-manifest/python",
    },
    "log": {
        "log_config": "true",
        "log_cffi": "false",
        "log_filesystem_storage": "false",
        "log_encfs": "false",
        "log_io": "false",
        "log_time": "false",
    },
    "ratls": {"enable": "false", "mrenclave": "", "mrsigner": ""},
    "profiler": {"enable_memory_profiler": "false", "memory_profiler_mode": "status"},
}

default_config = Configuration("config.ini", DEFUALTS_CONFIG_INI)

if default_config.getboolean("log", "log_config"):
    print("Config Loaded: ", default_config)
