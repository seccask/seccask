import sys
from daemon.message import Message
from daemon.coordinator import Coordinator

HOST = "127.0.0.1"
PORT = 50200

d = Coordinator(config={"ip": HOST, "port": PORT})


if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} EXP_NAME")
    sys.exit(1)


def start_exp(d: Coordinator):
    # d._main_loop.run_until_complete(d._on_msg("new_worker", None))
    d.emit_msg(Message("main", "start", [f"exp_{sys.argv[1]}"]))


d.on_start(start_exp)
d.start()
