"""seccask-exp: Start an experiment.

A self-contained script file to generate a shell command that starts the
coordinator given a list of options and the configuration file.
"""
import argparse
import os
import sys

HOME = "/home/mlcask"

os.environ["APP_HOME"] = os.getcwd()
sys.path.append("./pysrc")


class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, *args):
        sys.stdout.close()
        sys.stdout = self._original_stdout


with HiddenPrints():
    from pipeman.config import default_config as conf

parser = argparse.ArgumentParser(
    prog="seccask-exp",
    description="Start an experiment.",
    epilog="Other arguments are read from the configuration file.",
)
parser.add_argument("manifest")
parser.add_argument("--setup", required=True, choices=["untrusted", "direct", "sgx"])
parser.add_argument("--log-path", help="Path to log file. If not set, write to stdout")
parser.add_argument("--encfs", action="store_true", help="Enable EncFS")
parser.add_argument(
    "--vtune", action="store_true", help="Use Intel VTune to collect profiling data"
)
parser.add_argument(
    "--dry", action="store_true", help="Dry run (print command and exit)"
)
args = parser.parse_args()

if args.setup == "untrusted":
    env_vars = {
        "PYTHONHOME": f"{HOME}/sgx/lib/cpython-3.9.13-install",
        "PYTHONPATH": f"{HOME}/sgx/seccask2/pysrc",
        "OMP_NUM_THREADS": "8",
        "HDF5_USE_FILE_LOCKING": "FALSE",
    }

    gramine_path = " ".join([f"{k}='{v}'" for k, v in env_vars.items()])
    gramine_manifest_path = f"{HOME}/sgx/seccask2/build/bin/seccask"
elif args.setup == "direct":
    # gramine_path = "/usr/local/lib/x86_64-linux-gnu/gramine/direct/loader /usr/local/lib/x86_64-linux-gnu/gramine/direct/libpal.so init"
    gramine_path = "/usr/local/bin/gramine-direct"
    gramine_manifest_path = f"{HOME}/sgx/seccask2/gramine_manifest/seccask"
elif args.setup == "sgx":
    gramine_path = "/usr/local/bin/gramine-sgx"
    # gramine_path = "/usr/local/lib/x86_64-linux-gnu/gramine/sgx/loader /usr/local/lib/x86_64-linux-gnu/gramine/sgx/libpal.so init"
    gramine_manifest_path = f"{HOME}/sgx/seccask2/gramine_manifest/seccask"
else:
    raise ValueError("Invalid setup")

# COMMAND_ESCAPED = r"{{ env PYTHONDONTWRITEBYTECODE=1 {}{}{}cset shield --exec {} -- {} --coordinator --mode={} --manifest={} {}; }}"
COMMAND_ESCAPED = r"{{ env PYTHONDONTWRITEBYTECODE=1 {}{}{}env {} {} --coordinator --mode={} --manifest={} {}; }}"
command = COMMAND_ESCAPED.format(
    "SECCASK_DEBUG_ENCFS=1 " if conf.getboolean("log", "log_encfs") else "",
    "SECCASK_PROFILE_IO=1 " if conf.getboolean("log", "log_io") else "",
    "/usr/bin/time -v " if conf.getboolean("log", "log_time") else "",
    gramine_path,
    gramine_manifest_path,
    "ratls" if conf.getboolean("ratls", "enable") else "tls",
    args.manifest,
    "-k SECCASK_TEST_KEY " if args.encfs else "",
)

if args.log_path is not None:
    command += r" > {} 2>&1".format(args.log_path)


def sh_exec(command: str, show_command=True, dry_run=False):
    if show_command or dry_run:
        print(command)
    if not dry_run:
        os.system(command)


sh_exec(command, dry_run=args.dry)
