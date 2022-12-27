import pkg_resources
import os
import sys
import pprint


def list_packages():
    env = dict(str(ws).split() for ws in pkg_resources.working_set)
    return env


def get_package_module_map():
    package_module_map = {}

    for p in list_packages().keys():
        metadata_dir = pkg_resources.get_distribution(p).egg_info  # type:ignore
        if metadata_dir is None:
            continue
        # print(f"metadata_dir: {metadata_dir}")
        top_level_text_path = os.path.join(metadata_dir, "top_level.txt")
        if os.path.exists(top_level_text_path):
            modules = open(top_level_text_path).read().rstrip().split("\n")
            package_module_map[p] = modules

    return package_module_map


def get_module_package_map():
    mpmap = {}
    pmmap = get_package_module_map()
    for p in pmmap:
        for module in pmmap[p]:
            mpmap[module] = p

    return mpmap


def get_active_modules():
    return sys.modules.keys()


def get_active_packages():
    active_packages = {}
    packages = list_packages()
    mpmap = get_module_package_map()
    for am in get_active_modules():
        if am in mpmap:
            active_packages[mpmap[am]] = packages[mpmap[am]]
    return active_packages


__all__ = ["get_active_packages"]

if __name__ == "__main__":
    pprint.pprint(get_active_packages())
