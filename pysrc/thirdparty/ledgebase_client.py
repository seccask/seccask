from typing import Optional
from cffi import FFI
import os

from pipeman.config import default_config

__all__ = ["get_api"]


LEDGEBASE_BASE_PATH = default_config.get("storage_ledgebase", "base_path")

os.environ.update(
    {
        "USTORE_BIN": LEDGEBASE_BASE_PATH + "/bin",
        "USTORE_CONF": LEDGEBASE_BASE_PATH + "/conf",
        "USTORE_CONF_DATA_DIR": "ustore_data",
        "USTORE_CONF_FILE": LEDGEBASE_BASE_PATH + "/conf/config.cfg",
        "USTORE_CONF_HOST_FILE": "conf/workers.lst",
        "USTORE_HOME": LEDGEBASE_BASE_PATH,
        "USTORE_LOG": LEDGEBASE_BASE_PATH + "/log",
    }
)


def _get_so_path(so_name: str):
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ustore_release/lib", so_name
    )


def _is_cffi_log_enabled():
    return default_config.getboolean("log", "log_cffi")


LIBRARY_PATH = _get_so_path("libcustore.so")

ffi = FFI()
ffi.cdef(
    """
    char *execPut_C(char* key, char* branch, char* version, char* str, char* fname);
    char *execGet_C(char* key, char* branch, char* version, char* fname);
"""
)
C = ffi.dlopen(LIBRARY_PATH)


def _check_none(value: Optional[str]):
    if value is None:
        return ffi.NULL
    else:
        return ffi.new("char[]", value.encode("utf-8"))


def get(key, branch, version=None, fname=None) -> str:
    arg_key = _check_none(key)
    arg_branch = _check_none(branch)
    arg_version = _check_none(version)
    arg_fname = _check_none(fname)

    if _is_cffi_log_enabled():
        print(
            "C API call: Get K={}, B={}, V={}, F={}".format(key, branch, version, fname)
        )

    ## `ret` will be freed automatically, according to CFFI docs
    ret = C.execGet_C(arg_key, arg_branch, arg_version, arg_fname)
    ret = ffi.string(ret).decode("utf-8")

    if _is_cffi_log_enabled():
        print("C API returned: {}".format(ret))

    return ret


def put(key, branch, str=None, fname=None) -> str:
    arg_key = _check_none(key)
    arg_branch = _check_none(branch)
    arg_str = _check_none(str)
    arg_fname = _check_none(fname)

    if _is_cffi_log_enabled():
        print(
            "C API call: Put K={}, B={}, V=NULL, S={}, F={}".format(
                key, branch, str, fname
            )
        )

    ## `ret` will be freed automatically, according to CFFI docs
    ret = C.execPut_C(arg_key, arg_branch, ffi.NULL, arg_str, arg_fname)
    ret = ffi.string(ret).decode("utf-8")

    if _is_cffi_log_enabled():
        print("C API returned: {}".format(ret))

    return ret


def get_api():
    return get, put


if __name__ == "__main__":
    import time

    start_time = time.time()
    put("TEST_KEY1", "TEST_BRANCH1", "0123456789ABCDEF0123456789ABCDEF")
    print(f"duration: {time.time() - start_time}")

    start_time = time.time()
    put("TEST_KEY1", "TEST_BRANCH2", "123456789ABCDEF0123456789ABCDEF0")
    print(f"duration: {time.time() - start_time}")

    start_time = time.time()
    put("TEST_KEY2", "TEST_BRANCH1", "23456789ABCDEF0123456789ABCDEF01")
    print(f"duration: {time.time() - start_time}")

    start_time = time.time()
    put("TEST_KEY2", "TEST_BRANCH2", "3456789ABCDEF0123456789ABCDEF012")
    print(f"duration: {time.time() - start_time}")

    start_time = time.time()
    get("TEST_KEY1", "TEST_BRANCH1")
    print(f"duration: {time.time() - start_time}")

    start_time = time.time()
    get("TEST_KEY1", "TEST_BRANCH2")
    print(f"duration: {time.time() - start_time}")

    start_time = time.time()
    get("TEST_KEY2", "TEST_BRANCH1")
    print(f"duration: {time.time() - start_time}")

    start_time = time.time()
    get("TEST_KEY2", "TEST_BRANCH2")
    print(f"duration: {time.time() - start_time}")
