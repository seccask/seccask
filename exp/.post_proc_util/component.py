#!/usr/bin/python

import os

files = [f for f in os.listdir(".") if os.path.isfile(os.path.join(".", f))]

print(f"Files: {files}")

for file in sorted([log_file for log_file in files if log_file.startswith("sgx") and log_file.endswith(".log")]):
    print(file)
    component_count = 0
    with open(file) as f:
        for line in f:
            line = line.rstrip()
            if "NODE TIME" in line:# and not line.endswith("0"):
                component_count += 1
                if (component_count % 10 in [1, 4, 6, 8, 0]):
                    # print(line)
                    print(line.split(":")[-1].lstrip())
    print()
    print()
    print()