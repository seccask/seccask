import os
import re
import time
from abc import ABCMeta, abstractmethod
from typing import List, Match, Optional, Type, TypeVar

from pipeman.store.base_storage import BaseStorage, TransferDType

# from pipeman.store.ssh import SSHConnection
from pipeman.store.ustoreconf import UStoreCLIConstant, UStoreConf
from pipeman.utils import LogUtils, StringUtils


class BaseReturn(metaclass=ABCMeta):
    """UStore CLI Abstract Return Object.

    Raises:
        RuntimeError: If parsing failed
    """

    REGEX_HEADER = r"\[(?P<is_success>\S*)\s*\:\s*(?P<action_taken>\S*)\] (?P<body>.*)"

    @abstractmethod
    def _parse_content(self):
        """Parse content to get result."""
        pass

    def __init__(self, stdin, stdout, stderr) -> None:
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr
        self._constant = UStoreCLIConstant()
        self._stdout_text = ""
        self.is_success = False

        self._retrieve_raw_stdout()
        self._remove_ansi_color_escape()
        self.logger.debug(f"[Returned] {self._stdout_text}")
        self._parse_body()
        if self.is_success:
            self.values = self._parse_content()

    def _retrieve_raw_stdout(self) -> None:
        # IF USING_PARAMIKO=TRUE
        # for line in self._stdout.readlines():
        #     self._stdout_text = self._stdout_text + line

        # ELSE
        # No need to readlines() since it is already handled by SSHConnection
        self._stdout_text = self._stdout

    def _remove_ansi_color_escape(self) -> None:
        self._stdout_text = StringUtils.remove_ansi_color_escape(self._stdout_text)

    def _parse_body(self) -> None:
        parsed_stdout = re.search(self.REGEX_HEADER, self._stdout_text)
        if parsed_stdout is None:
            raise RuntimeError("stdout invalid")

        t = parsed_stdout["is_success"]
        self.is_success = True if t == self._constant.RET_SUCCESS else False
        self._stdout_text = parsed_stdout["body"]


class GetReturn(BaseReturn):
    # REGEX_VALUE = r"Value\<(?P<Type>\S*)\>\:\s\"(?P<Value>.*)\""
    REGEX_VALUE = r"Value\<(?P<Type>\S*)\>\:\s(?P<Value>.*)"
    REGEX_FILE = (
        r"Value\<(?P<Type>\S*)\>\:(.*)\-\-\>(.*)(?P<FileName>\S*)(.*)\[(?P<Size>\S*)\]"
    )

    def _parse_content(self) -> Match[str]:
        result = None

        if self._stdout_text.find("-->") == -1:  # A string type return
            self._stdout_text = self._stdout_text.replace('"', "")
            result = re.search(self.REGEX_VALUE, self._stdout_text)
        else:  # A file type return
            result = re.search(self.REGEX_FILE, self._stdout_text)

        if result is None:
            raise RuntimeError("UStore Get parse error")

        return result


class PutReturn(BaseReturn):
    def _parse_content(self) -> dict:
        return dict(item.split(": ") for item in self._stdout_text.split(", "))


class ListReturn(BaseReturn):
    REGEX_LIST = r".*\[(?P<List>.*)\]"

    def _parse_content(self) -> List[str]:
        list_string = re.search(
            self.REGEX_LIST, self._stdout_text.replace('"', "").replace(" ", "")
        )
        if list_string is None:
            raise RuntimeError("UStore ListKey parse error")
        return list_string["List"].split(",")


class HeadReturn(BaseReturn):
    REGEX_HEAD = r"Version\: (?P<Version>\S*)"

    def _parse_content(self) -> str:
        result = re.search(self.REGEX_HEAD, self._stdout_text)
        if result is None:
            raise RuntimeError("UStore Head parse error")
        return result["Version"]


class BranchReturn(BaseReturn):
    def _parse_content(self) -> str:
        return self._stdout_text


class MetaReturn(BaseReturn):
    REGEX_META = r".* Parents: \[(?P<Parents>[\S|\s]*)\]"

    def _parse_content(self) -> Optional[List[str]]:
        result = re.search(self.REGEX_META, self._stdout_text)
        if result is None:
            raise RuntimeError("UStore Meta parse error")

        result = result["Parents"].replace(" ", "")
        if result == "<null>":
            return None
        else:
            return result.split(",")


class MergeReturn(BaseReturn):
    REGEX_MERGE = r"Version\: (?P<Version>\S*)"

    def _parse_content(self) -> Match[str]:
        result = re.search(self.REGEX_MERGE, self._stdout_text)
        if result is None:
            raise RuntimeError("UStore Merge parse error")
        return result


R = TypeVar("R", bound=BaseReturn)


class UStoreCLI(BaseStorage):
    def __init__(self, ustore_config: UStoreConf, ustore_constant: UStoreCLIConstant):
        super().__init__()
        self._cli_config = ustore_config
        self._cli_constant = ustore_constant
        self.is_connected = False

    @property
    def config(self):
        return self._cli_config

    @property
    def constant(self):
        return self._cli_constant

    def dlopen_ledgebase_lib(self):
        from thirdparty.ledgebase_client import get_api

        self.custore_get, self.custore_put = get_api()

    def init_cpp_module(self):
        # Below module is created from pybind11 and thus have no source
        import cpp_glassdb # type: ignore

        self.custore_get, self.custore_put = cpp_glassdb.get, cpp_glassdb.put

    def connect_remote_ustore(self):
        if self.is_connected:
            return

        # ssh_client = SSHConnection(self.config)
        import paramiko

        ssh_key = paramiko.RSAKey.from_private_key_file(self.config.USTORE_KEY_PATH)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ## Use password
        # ssh_client.connect(
        #     hostname=self.config.USTORE_ADDR,
        #     username=self.config.USTORE_USERNAME,
        #     password="PASSWORD",
        # )

        ## Use publickey
        ssh_client.connect(
            hostname=self.config.USTORE_ADDR,
            username=self.config.USTORE_USERNAME,
            pkey=ssh_key,
        )

        self.is_connected = True
        self.sshclient = ssh_client

    def connect(self):
        # self.dlopen_ledgebase_lib()
        # self.connect_remote_ustore()
        self.init_cpp_module()
        return self

    def disconnect(self):
        if not self.is_connected:
            return self

        # self.sshclient.close()
        self.is_connected = False

    def put(self, key: str, branch: str, dtype: TransferDType, value: str):

        ## IF SSH
        # parameters = {self.config.OPT_KEY: key, self.config.OPT_BRANCH: branch}

        self._check_and_wait_connection_alive()

        if dtype == TransferDType.FILE:
            ## IF SSH
            # ## Transfer local file to remote server
            # ## This is essential for SGX environment since it does not support direct file transfer
            # local_file = value
            # remote_file = os.path.basename(local_file)
            # ftp_client = self.sshclient.open_sftp()
            # ftp_client.put(local_file, remote_file)
            # ftp_client.close()

            # parameters[self.config.OPT_FILE] = remote_file

            # ## Direct file transfer. Can enable if not in SGX
            # # parameters[self.config.OPT_FILE] = os.path.abspath(value)

            # ## Put the file on remote server to forkbase
            # cmd = self._format_command(self.config.CMD_PUT, parameters)

            ## IF LIB_SO
            return self._exec_put(key, branch, None, os.path.abspath(value))

        elif dtype == TransferDType.STRING:
            ## IF SSH
            # ## Put the value on remote server to forkbase
            # parameters[self.config.OPT_DATA_VALUE] = value

            # cmd = self._format_command(self.config.CMD_PUT, parameters)

            ## IF LIB_SO
            return self._exec_put(key, branch, value, None)

        ## IF SSH
        # cmd_ret = self._exec_command(cmd, PutReturn)
        # return cmd_ret

    def get(
        self,
        key: str,
        branch: str = None,
        hversion: str = None,
        dtype: TransferDType = TransferDType.STRING,
    ):
        """
        Raises:
            ValueError
        """
        parameters = {
            self.config.OPT_KEY: key,
        }

        # self._check_and_wait_connection_alive()

        # if hversion is not None:
        #     parameters[self.config.OPT_VERSION] = hversion
        # elif branch is not None:
        #     parameters[self.config.OPT_BRANCH] = branch
        # else:
        #     raise ValueError("Not specifying one of branch and hversion")

        if dtype == TransferDType.FILE:
            # set a temporary file on remote server
            remote_file = "{}-{}-{}".format(key, branch, time.time())
            local_file = os.path.join(self.config.sftp_temp_path, remote_file)

            ## IF SSH
            # parameters[self.config.OPT_FILE] = remote_file
            # cmd = self._format_command(self.config.CMD_GET, parameters)
            # cmd_ret = self._exec_command(cmd, GetReturn)

            ## IF LIB_SO
            cmd_ret = self._exec_get(key, branch, hversion, os.path.abspath(local_file))

            if cmd_ret and cmd_ret.is_success:
                return cmd_ret, local_file
            else:
                return cmd_ret, None

            # # when the file is extracted from forkbase successfully, initiate the file transfer
            # if cmd_ret and cmd_ret.is_success:
            #     ftp_client = self.sshclient.open_sftp()
            #     ftp_client.get(remote_file, local_file)
            #     ftp_client.close()
            #     return cmd_ret, local_file
            # else:
            #     return cmd_ret, None
        elif dtype == TransferDType.STRING:
            ## IF SSH
            # cmd = self._format_command(self.config.CMD_GET, parameters)
            # cmd_ret = self._exec_command(cmd, GetReturn)

            ## IF LIB_SO
            cmd_ret = self._exec_get(key, branch, hversion, None)

            if cmd_ret and cmd_ret.is_success and cmd_ret.values:
                return cmd_ret, cmd_ret.values["Value"]
            else:
                return cmd_ret, None

    def list_key(self):

        self._check_and_wait_connection_alive()

        cmd = self._format_command(self.config.CMD_LIST_KEY)
        cmd_ret = self._exec_command(cmd, ListReturn)
        return cmd_ret

    def head(self, key: str, branch: str):

        self._check_and_wait_connection_alive()

        cmd = self._format_command(
            self.config.CMD_HEAD,
            {self.config.OPT_KEY: key, self.config.OPT_BRANCH: branch},
        )
        cmd_ret = self._exec_command(cmd, HeadReturn)
        return cmd_ret

    def branch(
        self,
        key: str,
        new_branch: str,
        based_on_branch: str = None,
        refer_version: str = None,
    ):

        self._check_and_wait_connection_alive()

        parameters = {self.config.OPT_KEY: key, self.config.OPT_BRANCH: new_branch}

        if based_on_branch is not None:
            parameters[self.config.OPT_REF_BRANCH] = based_on_branch
        if refer_version is not None:
            parameters[self.config.OPT_REF_VERSION] = refer_version

        cmd = self._format_command(self.config.CMD_BRANCH, parameters)

        cmd_ret = self._exec_command(cmd, BranchReturn)

        return cmd_ret

    def list_branch(self, key: str):

        self._check_and_wait_connection_alive()

        parameters = {self.config.OPT_KEY: key}

        cmd = self._format_command(self.config.CMD_LIST_BRANCH, parameters)

        cmd_ret = self._exec_command(cmd, ListReturn)
        return cmd_ret

    def meta(self, key: str, version: str = None, branch: str = None):
        self._check_and_wait_connection_alive()

        if version is not None:
            parameters = {self.config.OPT_KEY: key, self.config.OPT_VERSION: version}
        elif branch is not None:
            parameters = {self.config.OPT_KEY: key, self.config.OPT_BRANCH: branch}
        else:
            return None

        cmd = self._format_command(self.config.CMD_META, parameters)

        cmd_ret = self._exec_command(cmd, MetaReturn)
        return cmd_ret

    def merge(
        self,
        key: str,
        head_branch: str,
        merge_branch: str,
        dtype: TransferDType,
        value: str,
    ):

        parameters = {
            self.config.OPT_KEY: key,
            self.config.OPT_BRANCH: head_branch,
            self.config.OPT_REF_BRANCH: merge_branch,
        }

        self._check_and_wait_connection_alive()

        if dtype == TransferDType.FILE:
            # Transfer local file to remote server
            local_file = value
            remote_file = os.path.basename(local_file)
            ftp_client = self.sshclient.open_sftp()
            ftp_client.put(local_file, remote_file)
            ftp_client.close()

            # Put the file on remote server to forkbase
            cmd = self._format_command_xargs_for_merge(
                self.config.CMD_MERGE, remote_file, parameters
            )
        elif dtype == TransferDType.STRING:
            # Put the value on remote server to forkbase
            parameters[self.config.OPT_DATA_VALUE] = value

            cmd = self._format_command(self.config.CMD_MERGE, parameters)

        cmd_ret = self._exec_command(cmd, MergeReturn)
        return cmd_ret

    def _exec_get(self, key, branch, hversion, fname):
        start_time = time.time()

        stdout = self.custore_get(key, branch, hversion, fname)
        result = GetReturn(None, stdout, None)

        self.logger.debug(
            "[TIME: {}] Get {} {} {} {}".format(
                time.time() - start_time, key, branch, hversion, fname
            )
        )
        return result

    def _exec_put(self, key, branch, str, fname):
        start_time = time.time()

        stdout = self.custore_put(key, branch, str, fname)
        result = PutReturn(None, stdout, None)

        self.logger.debug(
            "[TIME: {}] Put {} {} {} {}".format(
                time.time() - start_time, key, branch, str, fname
            )
        )
        return result

    def _exec_command(
        self, cmd: str, parse_class: Optional[Type[R]]
    ) -> Optional[BaseReturn]:
        retried_times = 0
        while True:
            try:
                self.logger.debug("[CMD: Retried {}] {}".format(retried_times, cmd))
                if not self.is_connected:
                    self.connect()

                start_time = time.time()
                stdin, stdout, stderr = self.sshclient.exec_command(
                    self.config.SSH_CLIENT_CMD_PREFIX + cmd
                )

                if parse_class is not None:
                    result = parse_class(stdin, stdout, stderr)
                    self.logger.debug(
                        "[TIME: {}] {}".format(time.time() - start_time, cmd)
                    )
                    return result

                stdout_text = ""
                for line in stdout.readlines():
                    stdout_text = stdout_text + line
                # self.logger.debug(
                #     "[Raw Returned] {}".format(retried_times, repr(stdout))
                # )
                self.logger.debug("[TIME: {}] {}".format(time.time() - start_time, cmd))
                self.logger.debug(
                    "[CMD: Retried {} Raw Returned] {}".format(
                        retried_times, stdout_text
                    )
                )
                return None

            except Exception as err:
                self.logger.error(
                    "[CMD: Retried {}] ERROR: {}".format(retried_times, err)
                )
                if retried_times >= int(self.config.MAX_RETRY_TIMES):
                    self.logger.error(
                        "[CMD: Retried {}] Exceed maximize retry times. Exit"
                    )
                    raise err

                self.disconnect()
                self.connect()
                retried_times += 1

    def _format_command(self, cmd: str, parameters: dict = None):
        ret_cmd = self.config.USTORE_CMD_CLI + " " + cmd
        if parameters is not None:
            for key, value in parameters.items():
                ret_cmd = ret_cmd + " " + key + " " + value

        return ret_cmd

    def _format_command_xargs_for_merge(
        self, cmd: str, file_name: str, parameters: dict = None
    ):
        """
        Temporary solution because UStore Merge command does not support config.OPT_FILE
        We use "-x" options reading from stdin instead
        example:
            cat {filename} | ustore_cli put -k {key_name} -b {branch_name} -x 
        """
        ret_cmd = (
            "cat"
            + " "
            + file_name
            + " | xargs "
            + self.config.USTORE_CMD_CLI
            + " "
            + cmd
        )
        if parameters is not None:
            for key, value in parameters.items():
                ret_cmd = ret_cmd + " " + key + " " + value

        # always last option
        ret_cmd = ret_cmd + " " + self.config.OPT_DATA_VALUE + " "

        return ret_cmd

    def exec_command(
        self, cmd: str, parse_class: Optional[Type[R]] = None, noparse=False
    ) -> Optional[BaseReturn]:
        # self._check_and_wait_connection_alive()
        if noparse == True:
            return self._exec_command(cmd, None)
        else:
            return self._exec_command(cmd, parse_class)

    def _check_and_wait_connection_alive(self):
        ## IF SSH_ADDR IS LOOPBACK
        pass

        ## Else
        # self.logger.debug("refresh connection")
        # if self.sshclient:
        #     self.disconnect()
        #     self.connect()
        # self._exec_command("ustore_cli size", noparse=True)


if __name__ == "__main__":

    cli = UStoreCLI(ustore_config=UStoreConf(), ustore_constant=UStoreCLIConstant())
    cli.connect()

    ret = cli.put(
        key="test_key",
        branch="master",
        dtype=TransferDType.STRING,
        value="master.content.1",
    )
    ret = cli.put(
        key="test_key",
        branch="master",
        dtype=TransferDType.STRING,
        value="master.content.2",
    )
    ret = cli.branch(key="test_key", new_branch="dev", based_on_branch="master")
    ret = cli.put(
        key="test_key",
        branch="master",
        dtype=TransferDType.STRING,
        value="master.content.3",
    )
    ret = cli.put(
        key="test_key", branch="dev", dtype=TransferDType.STRING, value="dev.content.1"
    )
    ret = cli.put(
        key="test_key", branch="dev", dtype=TransferDType.STRING, value="dev.content.2"
    )
    ret = cli.merge(
        key="test_key",
        head_branch="master",
        merge_branch="dev",
        dtype=TransferDType.STRING,
        value="merged-content",
    )

    print(ret.values if ret is not None else "ERROR")

    ret = cli.meta(key="test_key", version=ret.values if ret is not None else "ERROR")

    print(ret.values if ret is not None else "ERROR")
