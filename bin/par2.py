#!/usr/bin/env python3
"""Create or verify par2 recovery sets for every directory under a root path.

Walks the given directory bottom-up. With ``--create``, directories without
a ``.dir.par2`` recovery set get one created; directories that already have
one are always verified. Without ``--create``, directories without a
recovery set are skipped. With ``--json``, results are reported as a single
JSON object on stdout instead of human-readable text.

Exit status:
    0 -- everything is healthy
    1 -- warnings (skipped directories, recoverable errors, unprotected files)
    2 -- critical (usage error, missing directory, unrecoverable corruption)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

MAX_FILES: int = 32_000
PAR2_NAME: str = ".dir.par2"
RE_FILES: re.Pattern[str] = re.compile(r'Target: "(.*?)" - found.')

OK: int = 0
WARNING: int = 1
CRITICAL: int = 2
STATUS_NAME: dict[int, str] = {OK: "ok", WARNING: "warning", CRITICAL: "critical"}


def run_par2(command: str) -> str:
    """Run a par2 command through the shell and return its stdout."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
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
    all_files: list[str] = [f.name for f in dir_path.iterdir() if f.is_file()]

    if len(all_files) > MAX_FILES:
        emit(
            f"WARNING! Too many files in directory {dir_path}. "
            f"par2 handles max. {MAX_FILES}, skipping"
        )
        return WARNING
    # Hidden files (the par2 sets themselves and anything else) are not
    # protected, but the recovery set must still be detected below.
    file_list: list[str] = [f for f in all_files if not f.startswith(".")]

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

    par_output: str = run_par2(f"par2verify {dir_path}/{PAR2_NAME} {dir_path}/*")
    if "Repair is not possible." in par_output:
        emit(f"CRITICAL! Unrecoverable error in directory {dir_path}")
        return CRITICAL
    if "Repair is required." in par_output:
        emit(f"WARNING! Recoverable error in directory {dir_path}")
        return WARNING
    if "All files are correct, repair is not required." in par_output:
        par_files: set[str] = set(RE_FILES.findall(par_output))
        diff_files: list[str] = sorted(set(file_list) - par_files)
        if diff_files:
            emit(
                f"WARNING! Unprotected files in directory {dir_path}: "
                f"{','.join(diff_files)}"
            )
            return WARNING
    return OK


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="par2.py",
        description=(
            "Create or verify par2 recovery sets for every directory "
            "under a root path."
        ),
        epilog=(
            "Exit status: 0 = all healthy, 1 = warnings (skipped directories, "
            "recoverable errors, unprotected files), "
            "2 = critical (usage error, missing directory or unrecoverable "
            "corruption)."
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
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        dest="json_output",
        help=(
            "print a single JSON object with the overall status and "
            "per-directory results instead of human-readable text "
            "(intended for automation and LLM tool calls)"
        ),
    )
    return parser


def main(argv: list[str]) -> int:
    """Entry point: process every directory under the given root path."""
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args(argv[1:])
    if args.directory is None:
        parser.print_help()
        return CRITICAL

    root: Path = Path(args.directory)
    if not root.is_dir():
        message: str = f"CRITICAL! Not a directory: {args.directory}"
        if args.json_output:
            print(
                json.dumps(
                    {
                        "status": STATUS_NAME[CRITICAL],
                        "exit_code": CRITICAL,
                        "error": message,
                    }
                )
            )
        elif not args.silent:
            print(message)
        return CRITICAL

    status: int = OK
    directories: list[dict[str, object]] = []
    for dir_name, _, _ in os.walk(root, topdown=False):
        messages: list[str] = []
        dir_status: int = process_directory(
            Path(dir_name), create=args.create, emit=messages.append
        )
        status = max(status, dir_status)
        if args.json_output:
            directories.append(
                {
                    "path": str(dir_name),
                    "status": STATUS_NAME[dir_status],
                    "messages": messages,
                }
            )
        elif not args.silent:
            for message in messages:
                print(message)

    if args.json_output:
        print(
            json.dumps(
                {
                    "status": STATUS_NAME[status],
                    "exit_code": status,
                    "root": str(root),
                    "directories": directories,
                }
            )
        )
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
