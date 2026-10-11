#!/usr/bin/env python3
"""Create or verify par2 recovery sets for every directory under a root path.

Walks the given directory bottom-up. With ``--create``, directories without
a ``.dir.par2`` recovery set get one created; directories that already have
one are always verified. Without ``--create``, directories without a
recovery set are skipped.

Exit status:
    0 -- everything is healthy
    1 -- warnings (skipped directories, recoverable errors, unprotected files)
    2 -- critical (usage error or unrecoverable corruption)
"""

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Callable
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


def process_directory(
    dir_path: Path,
    *,
    create: bool = False,
    emit: Callable[[str], None] = print,
) -> int:
    """Create or verify the par2 set for a single directory.

    When ``create`` is set, directories without a recovery set get one;
    otherwise they are skipped. ``emit`` receives human-readable progress
    and warning messages -- pass a no-op to run quietly.

    Returns the status code for this directory: ``OK``, ``WARNING``
    or ``CRITICAL``.
    """
    all_files = [f.name for f in dir_path.iterdir() if f.is_file()]

    if len(all_files) > MAX_FILES:
        emit(
            f"WARNING! Too many files in directory {dir_path}. "
            f"par2 handles max. {MAX_FILES}, skipping"
        )
        return WARNING
    # Hidden files (the par2 sets themselves and anything else) are not
    # protected, but the recovery set must still be detected below.
    file_list = [f for f in all_files if not f.startswith(".")]

    if PAR2_NAME not in all_files:
        if not file_list:
            emit(f"Empty directory {dir_path}, skipping")
            return OK
        if not create:
            emit(f"No recovery set in directory {dir_path}, skipping")
            return OK
        emit(str(dir_path))
        emit(str(file_list))
        run_par2(f"par2create {dir_path}/{PAR2_NAME} {dir_path}/*")
        return OK

    par_output = run_par2(f"par2verify {dir_path}/{PAR2_NAME} {dir_path}/*")
    if "Repair is not possible." in par_output:
        emit(f"CRITICAL! Unrecoverable error in directory {dir_path}")
        return CRITICAL
    if "Repair is required." in par_output:
        emit(f"WARNING! Recoverable error in directory {dir_path}")
        return WARNING
    if "All files are correct, repair is not required." in par_output:
        par_files = set(RE_FILES.findall(par_output))
        diff_files = sorted(set(file_list) - par_files)
        if diff_files:
            emit(
                f"WARNING! Unprotected files in directory {dir_path}: "
                f"{','.join(diff_files)}"
            )
            return WARNING
    return OK


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="par2.py",
        description=(
            "Create or verify par2 recovery sets for every directory "
            "under a root path."
        ),
        epilog=(
            "Exit status: 0 = all healthy, 1 = warnings (skipped directories, "
            "recoverable errors, unprotected files), "
            "2 = critical (usage error or unrecoverable corruption)."
        ),
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="root directory to walk recursively",
    )
    parser.add_argument(
        "-c",
        "--create",
        action="store_true",
        help=(
            "create a missing recovery set instead of skipping the directory "
            "(existing sets are always verified)"
        ),
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        help="suppress all output and only report the exit status",
    )
    return parser


def main(argv: list[str]) -> int:
    """Entry point: process every directory under the given root path."""
    parser = build_parser()
    args = parser.parse_args(argv[1:])
    if args.directory is None:
        parser.print_help()
        return CRITICAL

    emit: Callable[[str], None] = (lambda _message: None) if args.silent else print

    status = OK
    for dir_name, _, _ in os.walk(args.directory, topdown=False):
        status = max(
            status,
            process_directory(Path(dir_name), create=args.create, emit=emit),
        )
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
