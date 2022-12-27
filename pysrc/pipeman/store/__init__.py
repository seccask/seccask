"""Storage Subsystem.

This module contains all supported storage methods, with different properties.
"""
from pipeman.config import default_config as conf
from pipeman.store.base_storage import BaseStorage

store: BaseStorage


__all__ = ["store"]


def use_forkbase():
    global store

    from pipeman.store.ustorecli import UStoreCLI
    from pipeman.store.ustoreconf import UStoreCLIConstant, UStoreConf

    store = UStoreCLI(ustore_config=UStoreConf(), ustore_constant=UStoreCLIConstant())


def use_filesystem():
    global store

    from pipeman.store.filesystem import FileSystemStorage

    store = FileSystemStorage()


def use_pep249():
    global store

    from pipeman.store.pep249 import PEP249Storage

    USER = conf.get("storage_rdbms", "user")
    SSL_CERT_PATH = conf.get("storage_rdbms", "ssl_cert_path")
    SSL_KEY_PATH = conf.get("storage_rdbms", "ssl_key_path")

    store = PEP249Storage(user=USER, ssl_cert=SSL_CERT_PATH, ssl_key=SSL_KEY_PATH)


def init_physical_storage():
    selected_storage = conf.get("storage", "storage_engine")
    if selected_storage == "forkbase":
        use_forkbase()
    # elif selected_storage == "ledgebase":
    #     use_ledgebase()
    elif selected_storage == "filesystem":
        use_filesystem()
    elif selected_storage == "rdbms":
        use_pep249()

    store.connect()


init_physical_storage()
