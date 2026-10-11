#!/usr/bin/env python3
"""Create or verify par2 recovery sets for every directory under a root path.

Walks the given directory bottom-up. Directories without a ``.dir.par2``
recovery set get one created; directories that already have one are verified.

Exit status:
    0 -- everything is healthy
    1 -- warnings (skipped directories, recoverable errors, unprotected files)
    2 -- critical (usage error or unrecoverable corruption)
"""

import os
import re
import subprocess
import sys
from pathlib import Path

MAX_FILES = 32_000
PAR2_NAME = ".dir.par2"
RE_FILES = re.compile(r'Target: "(.*?)" - found.')

OK = 0
WARNING = 1
CRITICAL = 2


def run_par2(command: str) -> str:
    """Run a par2 command through the shell and return its stdout."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def process_directory(dir_path: Path) -> int:
    """Create or verify the par2 set for a single directory.

    Returns the status code for this directory: ``OK``, ``WARNING``
    or ``CRITICAL``.
    """
    all_files = [f.name for f in dir_path.iterdir() if f.is_file()]

    if len(all_files) > MAX_FILES:
        print(
            f"WARNING! Too many files in directory {dir_path}. "
            f"par2 handles max. {MAX_FILES}, skipping"
        )
        return WARNING
    # Hidden files (the par2 sets themselves and anything else) are not
    # protected, but the recovery set must still be detected below.
    file_list = [f for f in all_files if not f.startswith(".")]

    if PAR2_NAME not in all_files:
        if not file_list:
            print(f"Empty directory {dir_path}, skipping")
            return OK
        print(dir_path)
        print(file_list)
        run_par2(f"par2create {dir_path}/{PAR2_NAME} {dir_path}/*")
        return OK

    par_output = run_par2(f"par2verify {dir_path}/{PAR2_NAME} {dir_path}/*")
    if "Repair is not possible." in par_output:
        print(f"CRITICAL! Unrecoverable error in directory {dir_path}")
        return CRITICAL
    if "Repair is required." in par_output:
        print(f"WARNING! Recoverable error in directory {dir_path}")
        return WARNING
    if "All files are correct, repair is not required." in par_output:
        par_files = set(RE_FILES.findall(par_output))
        diff_files = sorted(set(file_list) - par_files)
        if diff_files:
            print(
                f"WARNING! Unprotected files in directory {dir_path}: "
                f"{','.join(diff_files)}"
            )
            return WARNING
    return OK


def main(argv: list[str]) -> int:
    """Entry point: process every directory under ``argv[1]``."""
    if len(argv) < 2:
        print("Usage: par2.py <directory>")
        return CRITICAL

    status = OK
    for dir_name, _, _ in os.walk(argv[1], topdown=False):
        status = max(status, process_directory(Path(dir_name)))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
