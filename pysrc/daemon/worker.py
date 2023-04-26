import gc
import importlib.util
import os
import time
import sys
from typing import List

from profiler import mem_profiler


def execute_component(
    component_id: str, working_directory: str, cmds: List[str]
) -> str:
    print(f"[Worker] Changing working directory to: {working_directory}")
    os.chdir(working_directory)

    # add working directory to sys.path
    sys.path.append(working_directory)
    os.environ["PYTHONUNBUFFERED"] = "1"

    print(f"[Worker] Execute command: {cmds}")

    # ignore Literal["python"]
    cmds = cmds[1:]

    # retrive input and output folder
    inputfolder = ""
    outputfolder = ""
    for i, c in enumerate(cmds):
        if c == "--input":
            inputfolder = cmds[i + 1]
        if c == "--output":
            outputfolder = cmds[i + 1]

    # load user component code
    script_path = os.path.abspath(os.path.join(working_directory, cmds[0]))

    ### DEBUG: Read and print script content
    # with open(script_path, "r") as f:
    #     print(f.read())

    spec = importlib.util.spec_from_file_location("module.name", script_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(module)  # type: ignore

    # run code. the entry point is `def start(inputfolder, outputfolder) -> None`

    print(f"[Worker] TIME OF COMPONENT START: {time.time()}")
    module.start(inputfolder, outputfolder)

    del module

    gc.collect()

    print(f"[WM] Component {component_id} done")

    mem_profiler.profile()

    return component_id
