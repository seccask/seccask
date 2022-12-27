from typing import Any, List


class Message:
    def __init__(self, sender_id: str, cmd: str, args: List[Any] = []) -> None:
        self._sender_id = sender_id
        self._cmd = cmd
        self._args = args

    @property
    def sender_id(self):
        return self._sender_id

    @property
    def cmd(self):
        return self._cmd

    @property
    def args(self):
        return self._args

    def __repr__(self) -> str:
        return f"<MSG:From {self.sender_id}|{self.cmd} with args {self.args}>"

    def dump(self) -> bytearray:
        body = f"{self._sender_id}\r\n{self._cmd}\r\n{'%'.join(self.args)}"
        result = bytearray()
        result.extend(len(body).to_bytes(4, "big"))
        result.extend(map(ord, body))
        return result

    @staticmethod
    def load(msg_str: str):
        tokens = msg_str.split("\r\n")
        args = tokens[2].split("%")
        return Message(tokens[0], tokens[1], args)
