import socket
from typing import Optional, Tuple

from ssh2.session import Session

from pipeman.store.ustoreconf import UStoreConf


class SSHConnection:
    def __init__(self, conf: UStoreConf) -> None:
        self.conf = conf
        self.session = None

    def connect(self) -> None:
        # Make socket, connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.conf.USTORE_ADDR, 22))

        # Initialise
        self.session = Session()
        self.session.handshake(sock)

        # Convenience function for agent based authentication
        self.session.userauth_publickey_fromfile(
            self.conf.USTORE_USERNAME, self.conf.USTORE_KEY_PATH
        )

    def close(self) -> None:
        if self.session:
            self.session.disconnect()
            del self.session
            self.session = None

    def exec_command(self, cmd: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # Channel initialise, exec and wait for end
        if not self.session:
            self.connect()
        channel = self.session.open_session()  # type: ignore
        channel.execute(cmd)
        channel.wait_eof()
        channel.close()
        channel.wait_closed()
        result = self.get_stdout(channel)
        del channel
        return None, result, None

    def get_stdout_bytes(self, channel):
        size, data = channel.read()
        yield data
        while size > 0:
            size, data = channel.read()
            yield data

    # Print output
    def get_stdout(self, channel):
        result = ""
        for b in self.get_stdout_bytes(channel):
            result += b.decode("utf-8")
        return result

    def open_sftp(self):
        raise NotImplementedError()

    def put(self):
        raise NotImplementedError()
