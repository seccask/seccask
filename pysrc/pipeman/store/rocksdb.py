from typing import Union

import pyrocksdb


class RocksDBStorage:
    def __init__(self, path: str) -> None:
        print(f"RocksDBStorage initializing...")
        self.path = path
        self.db = pyrocksdb.DB()  # type: ignore
        self.opts = pyrocksdb.Options()  # type: ignore
        self.opts.create_if_missing = True
        # self.opts.advise_random_on_open = True
        self.ropts = pyrocksdb.ReadOptions()  # type: ignore
        self.wopts = pyrocksdb.WriteOptions()  # type: ignore
        print(f"RocksDBStorage initialized")

    def connect(self):
        status = self.db.open(self.opts, self.path)
        if status.ok():
            print(f"RocksDB connected")
            return
        else:
            raise RuntimeError(status.code())

    def disconnect(self):
        self.db.close()

    def get(self, key: str) -> Union[bytes, None]:
        ret = self.db.get(self.ropts, key.encode())
        if ret.status.ok():
            return ret.data
        else:
            return None

    def put(self, key: str, value: str) -> None:
        status = self.db.put(self.wopts, key.encode(), value.encode())
        if status.ok():
            return
        else:
            raise RuntimeError(status.code())


if __name__ == "__main__":
    db = RocksDBStorage(path="/mnt/pyrocksdb")
    db.connect()

    print("PREVIOUS: key=test_key, value=?")
    ret = db.get(key="test_key")
    print(f"ret: {ret}")
    print('RUNNING: db.put(key="test_key", value="master.content.1")')
    ret = db.put(key="test_key", value="master.content.1")
    print(f"ret: {ret}")
    print('RUNNING: db.get(key="test_key")')
    ret = db.get(key="test_key")
    print(f"ret: {ret}")
