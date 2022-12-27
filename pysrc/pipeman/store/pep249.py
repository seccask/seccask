import hashlib
import os
import threading
import time
from typing import List, Union

# replace this with other DB client if necessary
import mysql.connector as connector
from mysql.connector.errors import Error

from pipeman.store.base_storage import (
    BaseStorage,
    StorageReturn,
    TransferDType,
)
from pipeman.utils import LogUtils


class ConnectionPool:
    def __init__(self) -> None:
        super().__init__()
        self.logger = LogUtils.get_default_named_logger(type(self).__name__)
        self._objs = {}
        self._lock = threading.Lock()

    def connect(self, obj):
        conn_id = self._make_conn_id(obj.host, obj.port, obj.user)

        self._lock.acquire()

        if conn_id in self._objs:
            self.logger.debug(
                "[ConnectionPool] {} exists. Directly returned".format(conn_id)
            )
        else:
            self.logger.debug("[ConnectionPool] {} not exist. Creating".format(conn_id))
            obj._do_connect()
            self.logger.debug("[ConnectionPool] {} created".format(conn_id))

            self._objs[conn_id] = obj

        self._lock.release()

        return self._objs[conn_id]

    def disconnect(self, obj):
        conn_id = self._make_conn_id(obj.host, obj.port, obj.user)

        self._lock.acquire()

        if conn_id in self._objs:
            self.logger.debug("[ConnectionPool] {} closing".format(conn_id))
            self._objs[conn_id]._do_disconnect()
            self._objs[conn_id] = None
        else:
            # Do nothing. Or you can log this unusual behavior
            pass

        self._lock.release()

    def _make_conn_id(self, host, port, user):
        return f"{user}@{host}:{port}"


pool = ConnectionPool()


class PEP249Storage(BaseStorage):
    """Database storage subsystem following PEP 249.

    This is a storage subsystem using any database connector following [Python 
    Database API Specification v2.0](https://www.python.org/dev/peps/pep-0249/) 
    as its physical storage. 

    NOTE: DBMS is required to create a database called `seccask`, and create 
    tables using the following SQL query:

    CREATE TABLE blobstore (
        bs_key LONGTEXT,
        bs_branch LONGTEXT,
        bs_hversion CHAR(64),
        bs_blob_value LONGBLOB
    );

    CREATE TABLE head (
        h_key LONGTEXT,
        h_branch LONGTEXT,
        h_hversion CHAR(64)
    );
    """

    # TODO: Moved to dedicated config file
    CHUNKSIZE = 8192
    DATABASE_NAME = "seccask"
    TABLE_NAME = "blobstore"
    TEMP_PATH = "/home/mlcask/sgx/gemini-pipeline/gemini-pipeline/temp"

    def __init__(
        self,
        user: str,
        host: str = "127.0.0.1",
        port: int = 3306,
        password: Union[str, None] = None,
        ssl_cert: Union[str, None] = None,
        ssl_key: Union[str, None] = None,
    ) -> None:
        super().__init__()
        self.user = user
        self.host = host
        self.port = port
        self.password = password
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.is_connected = False

    def connect(self) -> BaseStorage:
        self.conn = pool.connect(self).conn
        self.is_connected = True
        return self

    def _check_and_connect(self):
        if not self.is_connected:
            self.connect()

    def _do_connect(self):
        if self.password is not None:
            self.conn = connector.connect(
                host=self.host,
                port=self.port,
                database=self.DATABASE_NAME,
                user=self.user,
                password=self.password,
                autocommit=True,
            )
        elif self.ssl_cert is not None and self.ssl_key is not None:
            self.conn = connector.connect(
                host=self.host,
                port=self.port,
                database=self.DATABASE_NAME,
                user=self.user,
                ssl_key=self.ssl_key,
                ssl_cert=self.ssl_cert,
                autocommit=True,
            )
        else:
            raise ConnectionError(
                f"Connection failed: {self.user}@{self.host}:{self.port}"
            )

    def disconnect(self):
        """Not proper to do any close-connection stuff before refactoring the 
        whole storage procedure
        """
        # pool.disconnect(self)
        pass

    def _do_disconnect(self):
        self.conn.close()

    def get(
        self,
        key: str,
        branch: str = None,
        hversion: str = None,
        dtype: TransferDType = TransferDType.STRING,
    ):
        self._check_and_connect()

        if hversion is not None:
            pass
        elif branch is not None:
            try_hversion = self._get_head_version(key, branch)
            if try_hversion is None:
                return None, None
            hversion = try_hversion
        else:
            raise ValueError("Not specifying one of branch and hversion")

        sql = (
            "SELECT bs_blob_value FROM blobstore WHERE bs_key = %s AND bs_hversion = %s"
        )
        cursor = self.conn.cursor(buffered=True)
        cursor.execute(sql, (key, hversion))

        if cursor.rowcount == 0:
            return None, None

        row = cursor.fetchall()[0]
        cursor.close()

        # set a temporary file on remote server
        file_path = os.path.join(self.TEMP_PATH, f"{time.time()}-{key}-{branch}")

        with open(file_path, "wb") as f:
            f.write(row[0])

        self.logger.debug(f"Get [{key}]::[{branch}] from dir: {file_path}")

        if dtype == TransferDType.FILE:
            return None, file_path

        elif dtype == TransferDType.STRING:
            with open(file_path, "r") as f:
                content = f.read()
            return None, content

    def _get_head_version(self, key: str, branch: str) -> Union[str, None]:
        sql = "SELECT h_hversion FROM head WHERE h_key = %s AND h_branch = %s"
        cursor = self.conn.cursor(buffered=True)
        cursor.execute(sql, (key, branch))

        if cursor.rowcount == 0:
            return None

        result = cursor.fetchall()[0][0]
        cursor.close()
        return result

    def _set_head_version(self, key: str, branch: str, hversion: str) -> None:
        try_hversion = self._get_head_version(key, branch)

        if try_hversion is None:
            sql = "INSERT INTO head (h_key, h_branch, h_hversion) VALUES (%s, %s, %s)"
            params = (key, branch, hversion)
        else:
            sql = "UPDATE head SET h_hversion = %s WHERE h_key = %s AND h_branch = %s"
            params = (hversion, key, branch)

        cursor = self.conn.cursor(buffered=True)
        cursor.execute(sql, params)
        cursor.close()

    def put(self, key: str, branch: str, dtype: TransferDType, value: str):
        self._check_and_connect()

        if dtype == TransferDType.FILE:
            hash_generator = hashlib.sha256()
            hash_generator.update(f"{time.time()}##{key}::{branch}::".encode())

            local_file_path = value

            with open(local_file_path, "rb") as rf:
                content = rf.read()

            hash_generator.update(content)

            hversion = hash_generator.hexdigest()

        elif dtype == TransferDType.STRING:
            content = value

            # Compute non-collisional SHA256 as hashed version
            hversion = hashlib.sha256(
                f"{time.time()}##{key}::{branch}::{content}".encode()
            ).hexdigest()

        sql = (
            "INSERT INTO blobstore (bs_key, bs_branch, bs_hversion, bs_blob_value) "
            + "VALUES (%s, %s, %s, %s)"
        )
        cursor = self.conn.cursor(buffered=True)
        cursor.execute(sql, (key, branch, hversion, content))
        cursor.close()

        self.logger.debug(f"Put [{key}]::[{branch}] to database")

        # Shift branch HEAD
        self._set_head_version(key, branch, hversion)

        ret = StorageReturn()
        ret.values["Version"] = hversion
        return ret

    def list_key(self):
        self._check_and_connect()

        sql = "SELECT DISTINCT h_key FROM head"
        cursor = self.conn.cursor(buffered=True)
        cursor.execute(sql)

        if cursor.rowcount == 0:
            return []

        result = cursor.fetchall().zip()[0]
        cursor.close()
        return result

    def head(self, key: str, branch: str):
        self._check_and_connect()

        ret = StorageReturn()
        ret.values["Version"] = self._get_head_version(key, branch)
        return ret

    def branch(
        self,
        key: str,
        new_branch: str,
        based_on_branch: str = None,
        refer_version: str = None,
    ):
        raise NotImplementedError()

    def list_branch(self, key: str) -> List[str]:
        self._check_and_connect()

        sql = "SELECT DISTINCT h_branch FROM head WHERE key = %s"
        cursor = self.conn.cursor(buffered=True)
        cursor.execute(sql, (key))

        if cursor.rowcount == 0:
            return []

        result = cursor.fetchall().zip()[0]
        cursor.close()
        return result

    def meta(self, key: str, version: str = None, branch: str = None):
        raise NotImplementedError()

    def merge(
        self,
        key: str,
        head_branch: str,
        merge_branch: str,
        dtype: TransferDType,
        value: str,
    ):
        raise NotImplementedError()
