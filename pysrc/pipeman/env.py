import logging
import os

from pipeman.config import default_config as conf

__all__ = ["env"]


class Env:
    CONFIG_FOLDER_PATH = ".conf"
    CONFIG_SECTION = "env"
    CONFIG_ENV_TEMP_PATH = "temp_path"

    def __init__(self):
        self.home = conf.get_app_home()

    @property
    def temp_path(self):
        return conf.get(self.CONFIG_SECTION, self.CONFIG_ENV_TEMP_PATH)

    @property
    def config_base(self):
        return os.path.join(self.home, self.CONFIG_FOLDER_PATH)


env = Env()

if __name__ == "__main__":
    env = Env()
    logging.basicConfig(level=logging.DEBUG)
    logging.info(env.home)
    logging.info(env.temp_path)
