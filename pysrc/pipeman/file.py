import configparser
from datetime import datetime
import gc
import json
import os
import tempfile
from distutils import dir_util
from typing import Union

# import pathlib
# import zipfile
# import thirdparty.cpython.zipfile as zipfile
from thirdparty.stream_zip import stream_zip as sz
from thirdparty.stream_unzip_orig import stream_unzip as su

from pipeman.utils import LogUtils


# def traverse_directory(root: pathlib.Path):
#     for sub in root.iterdir():
#         if sub.is_dir():
#             yield from traverse_directory(sub)
#         else:
#             yield str(sub)
#             del sub


class PseudoDirEntry:
    def __init__(self, path: str):
        self.path = path
        self.is_dir = lambda: os.path.isdir(self.path)
        self.stat = lambda: os.stat(self.path)


def traverse_directory(root: Union[PseudoDirEntry, os.DirEntry]):
    if not root.is_dir():
        yield root
        return
    for entry in os.scandir(root.path):
        yield from traverse_directory(entry)


def iter_metadata_for_dir(root: str):
    for p in traverse_directory(PseudoDirEntry(root)):
        # for p in traverse_directory(pathlib.Path(".")):

        # dt = datetime.fromtimestamp(
        #     p.stat().st_mtime, tz=timezone.utc
        # )
        dt = datetime.now()
        # print(f"{p.path}: {dt.strftime('%Y-%m-%d-%H:%M')}")
        yield f"./{p.path}", dt, p.stat().st_mode & 0b111111111, sz.NO_COMPRESSION_64


def iter_metadata_for_file(path: str):
    e = PseudoDirEntry(path)
    yield path, e.stat().st_mtime, e.stat().st_mode & 0b111111111, sz.NO_COMPRESSION_64


def iter_stream_zip(root: str):
    for path, modified_at, perm, attr in iter_metadata_for_dir(root):
        f = open(path, "rb")
        yield path, modified_at, perm, attr, f
        f.close()


def iterate_binary(file_path: str):
    with open(file_path, "rb") as f:
        bytes = f.read(65536)
        while bytes:
            # Do stuff with byte.
            yield bytes
            bytes = f.read(65536)


def check_or_create_dir(directory: str) -> None:
    if directory == "":
        return
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def goto_dir(directory: str) -> str:
    """Create `directory` if not exist, cd to it, then returns old pwd"""
    old_pwd = os.getcwd()
    check_or_create_dir(directory)
    os.chdir(directory)
    return old_pwd


class FileUtils:
    logger = LogUtils.get_default_named_logger("FileUtils")

    @classmethod
    def open_local_config(cls, source_path) -> configparser.ConfigParser:
        with open(source_path, "r") as target_manifest_file:
            target_manifest_config = configparser.ConfigParser()
            target_manifest_config.read_file(target_manifest_file)

            cls.logger.info("Manifest Sections:")
            cls.logger.info(target_manifest_config.sections())

        return target_manifest_config

    @classmethod
    def write_local_config(
        cls, target_config: configparser.ConfigParser, dest_path: str
    ):
        with open(dest_path, "w") as target_manifest_file:
            target_config.write(target_manifest_file)
            cls.logger.info("{} written".format(dest_path))

    @classmethod
    def archive_local_file(cls, source_files: Union[list, str], dest_archive: str):
        cls.logger.debug(
            "Archiving file(s) {} to {}".format(source_files, dest_archive)
        )

        with open(dest_archive, "wb") as f:
            if isinstance(source_files, list):
                for zipped_chunk in sz.stream_zip(
                    [iter_metadata_for_file(p) for p in source_files]
                ):
                    f.write(zipped_chunk)
            elif isinstance(source_files, str):
                for zipped_chunk in sz.stream_zip(
                    [iter_metadata_for_file(source_files)]
                ):
                    f.write(zipped_chunk)
            else:
                raise ValueError("invalid source files")

        # with zipfile.ZipFile(dest_archive, "w") as archive:
        #     if isinstance(source_files, list):
        #         for p in source_files:
        #             archive.write(p)
        #     elif isinstance(source_files, str):
        #         archive.write(source_files)
        #     else:
        #         raise ValueError("invalid source files")

        ## GC to free memory during archive
        gc.collect()

    @classmethod
    def archive_local_folder(
        cls, source_folder: str, dest_archive: str, remove_base: bool = True
    ):
        cls.logger.debug(
            "Archiving folder {} to {}".format(source_folder, dest_archive)
        )
        old_pwd = goto_dir(source_folder)

        with open(dest_archive, "wb") as f:
            for zipped_chunk in sz.stream_zip(iter_stream_zip(".")):
                f.write(zipped_chunk)

        ## GC to free memory during archive
        gc.collect()

        goto_dir(old_pwd)

    @classmethod
    def extract_archive_to(cls, source_path: str, dest_path: str):
        cls.logger.debug("Extracting {} to {}".format(source_path, dest_path))
        old_pwd = goto_dir(dest_path)

        for file_name, file_size, unzipped_chunks in su.stream_unzip(
            iterate_binary(source_path)
        ):
            file_name = os.path.abspath(file_name)
            # cls.logger.debug("Extracting in dir {}: {}".format(dest_path, file_name))
            check_or_create_dir(os.path.dirname(file_name).decode("utf-8"))
            with open(file_name, "wb") as f:
                for chunk in unzipped_chunks:
                    f.write(chunk)
        ## GC to free memory during archive
        gc.collect()

        goto_dir(old_pwd)

    @staticmethod
    def dump_params_to(params: dict, dest_path: str):
        with open(dest_path, "w") as file:
            json.dump(params, file)

    @staticmethod
    def load_params_from(source_path: str) -> dict:
        with open(source_path, "r") as file:
            param = json.load(file)
        return param

    @staticmethod
    def copy_file_recursive(source_path: str, dest_path: str):
        dir_util.copy_tree(source_path, dest_path)

    @staticmethod
    def get_dir_size(path) -> int:
        size = 0
        for root, dirs, files in os.walk(path):
            size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
        return size

    @staticmethod
    def get_file_size(path) -> int:
        return os.path.getsize(path)

    @staticmethod
    def get_dir_compressed_size(path) -> int:
        size = 0
        with tempfile.NamedTemporaryFile() as fp:
            print("get_dir_compressed_size: compress {} to {}".format(path, fp.name))
            FileUtils.archive_local_folder(source_folder=path, dest_archive=fp.name)
            size = os.path.getsize(fp.name)
        return size

    @staticmethod
    def get_file_compressed_size(path) -> int:
        size = 0
        with tempfile.NamedTemporaryFile() as fp:
            print("get_file_compressed_size: compress {} to {}".format(path, fp.name))
            FileUtils.archive_local_file(source_files=path, dest_archive=fp.name)
            size = os.path.getsize(fp.name)
        return size
