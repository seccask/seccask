"""
Meta Classes
"""
import configparser
import json
import re
from typing import List

from pipeman.version import SemanticVersion

# NOTE:
# 1. version = branch.api_version.inc_version
# e.g. 'master.3.5'
#   should the physical storage layer uses forkbase, a mapping between version and
#   forkbase hashed version (hversion) should be mantained


class MetaKey:
    GENERIC_DATASET_KEY = "dataset"
    GENERIC_LIBRARY_KEY = "library"
    GENERIC_WORKSPACE_KEY = "workspace"
    GENERIC_SOLUTION_KEY = "solution"

    CURRENT_WORKSPACE_NAME = "current-workspace"

    def __init__(
        self,
        component_type: str,
        component_name: str,
        component_version: SemanticVersion = SemanticVersion.build_zero_version(),
    ):
        self._component_type = component_type
        self._component_name = component_name
        self._component_version = component_version

    @property
    def component_name(self) -> str:
        return self._component_name

    @component_name.setter
    def component_name(self, val: str):
        self._component_name = val

    @property
    def component_type(self) -> str:
        return self._component_type

    @component_type.setter
    def component_type(self, val: str):
        self._component_type = val

    @property
    def component_version(self) -> SemanticVersion:
        return self._component_version

    @component_version.setter
    def component_version(self, val: SemanticVersion):
        self._component_version = val

    # Note:
    # Generate keys for storage

    def to_string(self, with_version: bool = False):
        if with_version:
            return f"{self.component_type}::{self.component_name}::{self.component_version.version_str}"
        else:
            return f"{self.component_type}::{self.component_name}"

    @classmethod
    def build_from_string(cls, value: str, with_version: bool) -> "MetaKey":
        """
        Raises:
            ValueError
        """
        if with_version:
            result = re.match(r"(\S+)\:\:(\S+)\:\:(\S+)\.(\d+)\.(\d+)", value)
            if result is None:
                raise ValueError(f"cannot build semantic version from string '{value}'")
            return cls(
                result.group(1),
                result.group(2),
                SemanticVersion(
                    result.group(3), int(result.group(4)), int(result.group(5))
                ),
            )
        else:
            result = re.match(r"(\S+)\:\:(\S+)", value)
            if result is None:
                raise ValueError(f"cannot build semantic version from string '{value}'")
            return cls(result.group(1), result.group(2))

    @classmethod
    def build_current_workspace_meta_key(cls):
        return cls(cls.GENERIC_WORKSPACE_KEY, cls.CURRENT_WORKSPACE_NAME)

    @classmethod
    def build_generic_dataset_key(cls, name, sv):
        return cls(
            component_type=cls.GENERIC_DATASET_KEY,
            component_name=name,
            component_version=sv,
        )

    @classmethod
    def build_generic_library_key(cls, name, sv):
        return cls(
            component_type=cls.GENERIC_LIBRARY_KEY,
            component_name=name,
            component_version=sv,
        )

    @classmethod
    def build_generic_solution_key(cls, name, sv):
        return cls(
            component_type=cls.GENERIC_SOLUTION_KEY,
            component_name=name,
            component_version=sv,
        )

    @classmethod
    def build_generic_workspace_key(cls, name, sv):
        return cls(cls.GENERIC_WORKSPACE_KEY, name, sv)

    def api_version_equal_to(self, key):
        return key.component_version.api_version == self.component_version.api_version

    def type_name_equal_to(self, key):
        return (
            key.component_type == self.component_type
            and key.component_name == self.component_name
        )

    def has_update_over(self, key):
        if key.component_version.inc_version < self.component_version.inc_version:
            return True
        if key.component_version.api_version < self.component_version.api_version:
            return True
        if key.component_version.branch != self.component_version.branch:
            return True
        return False

    def has_major_update_over(self, key):
        if key.component_version.branch != self.component_version.branch:
            return True
        if key.component_version.api_version != self.component_version.api_version:
            return True
        return False

    def equals(self, key):
        return self.type_name_equal_to(key) and self.component_version.equals(
            key.component_version
        )

    def __str__(self):
        return self.to_string(with_version=True)

    def __repr__(self):
        return self.to_string(with_version=True)

    def __eq__(self, other):
        if isinstance(other, MetaKey):
            return self.equals(other)
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.to_string(with_version=True))


class MetaConfig:
    META_SECTION_ID = "identifier"

    META_ID_NAME = "name"
    META_ID_VERSION = "version"
    META_ID_CREATED_TIMESTAMP = "created-timestamp"
    META_ID_DESCRIPTION = "description"

    META_ID_META_TYPE = "type"

    def __init__(self, config: configparser.ConfigParser):
        self._icp = config
        if not self._icp.has_section(self.META_SECTION_ID):
            self._icp.add_section(self.META_SECTION_ID)

    @property
    def icp(self) -> configparser.ConfigParser:
        return self._icp

    @property
    def name(self) -> str:
        return self._icp.get(self.META_SECTION_ID, self.META_ID_NAME)

    @name.setter
    def name(self, val: str):
        self._icp.set(self.META_SECTION_ID, self.META_ID_NAME, val)

    @property
    def version(self) -> SemanticVersion:
        return SemanticVersion.from_version_str(
            self._icp.get(self.META_SECTION_ID, self.META_ID_VERSION)
        )

    @version.setter
    def version(self, val: SemanticVersion):
        self._icp.set(self.META_SECTION_ID, self.META_ID_VERSION, val.version_str)

    @property
    def meta_type(self) -> str:
        return self._icp.get(self.META_SECTION_ID, self.META_ID_META_TYPE)

    @meta_type.setter
    def meta_type(self, val: str):
        self._icp.set(self.META_SECTION_ID, self.META_ID_META_TYPE, val)

    @property
    def description(self):
        return self._icp.get(self.META_SECTION_ID, self.META_ID_DESCRIPTION)

    @description.setter
    def description(self, val: str):
        self._icp.set(self.META_SECTION_ID, self.META_ID_DESCRIPTION, val)

    @property
    def created_timestamp(self):
        return self._icp.getfloat(self.META_SECTION_ID, self.META_ID_CREATED_TIMESTAMP)

    @created_timestamp.setter
    def created_timestamp(self, val: float):
        self._icp.set(self.META_SECTION_ID, self.META_ID_CREATED_TIMESTAMP, str(val))

    def format_to_string(self) -> str:
        return f"{self.meta_type}/{self.name}:{self.version}"

    @property
    def internal_configure_parser(self) -> configparser.ConfigParser:
        return self._icp

    @property
    def key(self) -> MetaKey:
        return MetaKey(
            component_type=self.meta_type,
            component_name=self.name,
            component_version=self.version,
        )


class DatasetMeta(MetaConfig):
    META_TYPE = MetaKey.GENERIC_DATASET_KEY

    META_SECTION_CONFIG = "configuration"
    META_CONFIG_FILES = "files"
    META_CONFIG_DB_CONFIG = "db-config"
    META_CONFIG_SCHEMA_HASH = "schema-hash"

    def __init__(self, config: configparser.ConfigParser):
        super().__init__(config)

    # TODO: may change to dict type to represent multiple files
    @property
    def files(self) -> list:
        return self.icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_FILES).split(",")

    # TODO: database connection string
    @property
    def db_config(self) -> str:
        return self.icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_DB_CONFIG)

    @property
    def schema_hash(self) -> str:
        return self.icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_SCHEMA_HASH)

    @schema_hash.setter
    def schema_hash(self, val: str):
        self.icp.set(self.META_SECTION_CONFIG, self.META_CONFIG_SCHEMA_HASH, val)


class LibraryMeta(MetaConfig):
    META_TYPE = MetaKey.GENERIC_LIBRARY_KEY

    META_SECTION_CONFIG = "configuration"
    META_CONFIG_API_UPDATED = "api-version-updated"
    META_CONFIG_FILES = "files"
    META_CONFIG_SCRIPT_TRAIN = "train"
    META_CONFIG_SCRIPT_INFERENCE = "inference"
    META_CONFIG_PARAMETERS_TRAIN = "train-parameters"
    META_CONFIG_PARAMETERS_INFERENCE = "inference-parameters"

    def __init__(self, config: configparser.ConfigParser):
        super().__init__(config)

    @property
    def api_updated(self) -> bool:
        return super().icp.getboolean(
            self.META_SECTION_CONFIG, self.META_CONFIG_API_UPDATED
        )

    @property
    def train_script(self) -> str:
        return super().icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_SCRIPT_TRAIN)

    @property
    def train_params(self) -> dict:
        return json.loads(
            super().icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_PARAMETERS_TRAIN)
        )

    @property
    def inference_script(self) -> str:
        return super().icp.get(
            self.META_SECTION_CONFIG, self.META_CONFIG_SCRIPT_INFERENCE
        )

    @property
    def inference_params(self) -> dict:
        return json.loads(
            super().icp.get(
                self.META_SECTION_CONFIG, self.META_CONFIG_PARAMETERS_INFERENCE
            )
        )


class WorkspaceMeta(MetaConfig):
    META_TYPE = MetaKey.GENERIC_WORKSPACE_KEY

    META_SECTION_DATASETS = "datasets"
    META_DATASETS_TRAIN = "train"
    META_DATASETS_VALIDATION = "validation"
    META_DATASETS_INFERENCE = "inference"

    META_DATASET_ENUM = {
        META_DATASETS_TRAIN,
        META_DATASETS_VALIDATION,
        META_DATASETS_INFERENCE,
    }

    META_SECTION_SOLUTION = "solution"
    META_SOLUTION_KEY = "solution-key"

    META_SECTION_PATHS = "paths"
    META_PATHS_TEMP = "temp"
    META_PATHS_OUTPUT = "output"
    META_PATHS_BASE = "base"
    META_PATHS_VENV = "venv"

    META_PATH_ENUM = {
        META_PATHS_BASE,
        META_PATHS_OUTPUT,
        META_PATHS_TEMP,
        META_PATHS_VENV,
    }

    META_SECTION_CONFIG = "configuration"
    META_CONFIG_WORKSPACE_TYPE = "workspace-type"
    META_CONFIG_WORKSPACE_TYPE_PRODUCTION = "production-pipeline"
    META_CONFIG_WORKSPACE_TYPE_RETROSPECTIVE = "retrospective-pipeline"
    META_CONFIG_SHORT_BRANCH_IDENTIFIER = "short-branch-identifier"
    META_CONFIG_DESCRIPTION = "description"

    META_SECTION_REF = "reference"
    META_REF_PARAM = "params"
    META_REF_OUTPUT = "output"
    META_REF_PIPELINE = "pipeline"

    def __init__(self, config: configparser.ConfigParser):
        super().__init__(config)

    def init_sections(self):
        # self.icp.add_section(super().META_SECTION_ID)
        self.icp.add_section(self.META_SECTION_DATASETS)
        self.icp.add_section(self.META_SECTION_SOLUTION)
        self.icp.add_section(self.META_SECTION_PATHS)
        self.icp.add_section(self.META_SECTION_CONFIG)
        self.icp.add_section(self.META_SECTION_REF)

    @property
    def short_branch_identifier(self):
        return self.icp.get(
            self.META_SECTION_CONFIG, self.META_CONFIG_SHORT_BRANCH_IDENTIFIER
        )

    @short_branch_identifier.setter
    def short_branch_identifier(self, val: str):
        self.icp.set(
            self.META_SECTION_CONFIG, self.META_CONFIG_SHORT_BRANCH_IDENTIFIER, val
        )

    @property
    def description(self):
        return self.icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_DESCRIPTION)

    @description.setter
    def description(self, val: str):
        self.icp.set(self.META_SECTION_CONFIG, self.META_CONFIG_DESCRIPTION, val)

    # NOTE:
    # META_REF_PARAM / META_REF_OUTPUT / META_REF_PIPELINE are json strings
    # META_REF_PRRAM: dict (key, hversion)
    # META_REF_OUTPUT: dict (key, hversion)
    # META_REF_PIPELINE: list of key with semantic version
    @property
    def params(self) -> dict:
        return json.loads(self.icp.get(self.META_SECTION_REF, self.META_REF_PARAM))

    @params.setter
    def params(self, val: dict):
        self.icp.set(self.META_SECTION_REF, self.META_REF_PARAM, json.dumps(val))

    @property
    def outputs(self) -> dict:
        return json.loads(self.icp.get(self.META_SECTION_REF, self.META_REF_OUTPUT))

    @outputs.setter
    def outputs(self, val: dict):
        self.icp.set(self.META_SECTION_REF, self.META_REF_OUTPUT, json.dumps(val))

    @property
    def pipeline(self) -> List[MetaKey]:
        str_list = json.loads(
            self.icp.get(self.META_SECTION_REF, self.META_REF_PIPELINE)
        )
        return [
            MetaKey.build_from_string(value=str_val, with_version=True)
            for str_val in str_list
        ]

    @pipeline.setter
    def pipeline(self, val: list):
        str_list = [key.to_string(with_version=True) for key in val]
        self.icp.set(
            self.META_SECTION_REF, self.META_REF_PIPELINE, json.dumps(str_list)
        )

    #

    @property
    def solution(self) -> MetaKey:
        rawtext = self.icp.get(self.META_SECTION_SOLUTION, self.META_SOLUTION_KEY)
        return MetaKey.build_from_string(rawtext, with_version=False)

    @solution.setter
    def solution(self, solution: MetaKey):
        self.icp.set(
            self.META_SECTION_SOLUTION, self.META_SOLUTION_KEY, solution.to_string()
        )

    def get_dataset(self, whichdataset) -> MetaKey:
        """
        Raises:
            NoSectionError, NoOptionError
        """
        rawtext = self.icp.get(self.META_SECTION_DATASETS, whichdataset)
        return MetaKey.build_from_string(rawtext, with_version=False)

    def set_dataset(self, whichdataset, dataset: MetaKey):
        rawtext = dataset.to_string(with_version=False)
        self.icp.set(self.META_SECTION_DATASETS, whichdataset, rawtext)

    @property
    def datasets(self) -> dict:
        ddict = dict()
        for whichdataset in self.META_DATASET_ENUM:
            try:
                ddict[whichdataset] = self.get_dataset(whichdataset)
            except:
                ddict[whichdataset] = None
        return ddict

    @datasets.setter
    def datasets(self, ddict):
        for whichdataset in self.META_DATASET_ENUM:
            if whichdataset in ddict and ddict[whichdataset] is not None:
                self.set_dataset(whichdataset, ddict[whichdataset])

    def get_path(self, whichpath):
        """
        Raises:
            NoSectionError, NoOptionError
        """
        return self.icp.get(self.META_SECTION_PATHS, whichpath)

    def set_path(self, whichpath, path):
        try:
            self.icp.set(self.META_SECTION_PATHS, whichpath, path)
        except:
            pass

    @property
    def paths(self) -> dict:
        pdict = dict()
        for whichpath in self.META_PATH_ENUM:
            try:
                pdict[whichpath] = self.get_path(whichpath)
            except:
                pdict[whichpath] = None
        return pdict

    @paths.setter
    def paths(self, pdict):
        for whichpath in self.META_PATH_ENUM:
            if not pdict[whichpath] is None:
                self.set_path(whichpath, pdict[whichpath])

    @property
    def workspace_type(self):
        return self.icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_WORKSPACE_TYPE)

    @workspace_type.setter
    def workspace_type(self, val: str):
        if (
            val == self.META_CONFIG_WORKSPACE_TYPE_PRODUCTION
            or val == self.META_CONFIG_WORKSPACE_TYPE_RETROSPECTIVE
        ):
            self.icp.set(self.META_SECTION_CONFIG, self.META_CONFIG_WORKSPACE_TYPE, val)
        else:
            raise ValueError(val + "illegal")

    @property
    def is_retrospective(self) -> bool:
        return self.workspace_type == self.META_CONFIG_WORKSPACE_TYPE_RETROSPECTIVE

    @property
    def is_production(self) -> bool:
        return self.workspace_type == self.META_CONFIG_WORKSPACE_TYPE_PRODUCTION

    @property
    def physical_branch(self) -> str:
        """
        Raises:
            AttributeError, ValueError
        """
        if self.is_retrospective:
            return self.data_schema + "-" + self.short_branch_identifier
        elif self.is_production:
            return self.data_schema + "-" + "production"
        else:
            raise ValueError(f"not supported workspace type {self.workspace_type}")

    @property
    def data_schema(self) -> str:
        """
        Raises:
            AttributeError
        """
        return self.pipeline[0].component_version.branch

    def __str__(self) -> str:
        out_str = ""
        for key in self.pipeline:
            out_str = out_str + f"{key} -->"
        return out_str

    def __repr__(self) -> str:
        out_str = ""
        for key in self.pipeline:
            out_str = out_str + f"{key} -->"
        return out_str


class SolutionMeta(MetaConfig):
    META_TYPE = MetaKey.GENERIC_SOLUTION_KEY

    META_SECTION_CONFIG = "configuration"
    META_CONFIG_PREPROCESS_LIST = "preprocess-list"
    META_CONFIG_MODEL = "model"

    def __init__(self, config: configparser.ConfigParser):
        super().__init__(config)

    def init_sections(self):
        self.icp.add_section(super().META_SECTION_ID)
        self.icp.add_section(self.META_SECTION_CONFIG)

    @property
    def preprocess(self) -> list:
        raw_text = self.icp.get(
            self.META_SECTION_CONFIG, self.META_CONFIG_PREPROCESS_LIST
        )
        names_list = [
            MetaKey.build_from_string(y, with_version=False)
            for y in (x.strip() for x in raw_text.splitlines())
            if y
        ]
        return names_list

    @preprocess.setter
    def preprocess(self, component_list: list):
        raw_text = "\n".join([x.to_string(with_version=False) for x in component_list])
        self.icp.set(
            self.META_SECTION_CONFIG, self.META_CONFIG_PREPROCESS_LIST, raw_text
        )

    def append_preprocess(self, preprocess):
        component_list = self.preprocess
        component_list.append(preprocess)
        self.preprocess = component_list

    def remove_preprocess(self, preprocess):
        component_list = self.preprocess
        component_list.remove(preprocess)
        self.preprocess = component_list

    @property
    def model(self):
        raw_text = self.icp.get(self.META_SECTION_CONFIG, self.META_CONFIG_MODEL)
        return MetaKey.build_from_string(raw_text, with_version=False)

    @model.setter
    def model(self, model):
        self.icp.set(
            self.META_SECTION_CONFIG, self.META_CONFIG_MODEL, model.to_string()
        )

