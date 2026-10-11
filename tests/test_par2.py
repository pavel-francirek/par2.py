"""End-to-end and unit tests for the par2.py directory integrity script."""

import subprocess
import sys
from pathlib import Path

import pytest

import par2

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "par2.py"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the par2.py script as a subprocess and capture its output."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def make_tree(root: Path) -> None:
    """Create a small directory tree with files in the root and a subdir."""
    (root / "a.txt").write_text("hello\n")
    subdir = root / "sub"
    subdir.mkdir()
    (subdir / "b.txt").write_text("world\n")


def test_run_par2_captures_stdout() -> None:
    assert par2.run_par2("echo hello").strip() == "hello"


def test_no_arguments_prints_usage() -> None:
    result = run_script()
    assert result.returncode == par2.CRITICAL
    assert "Usage:" in result.stdout


def test_creates_par2_sets(tmp_path: Path) -> None:
    make_tree(tmp_path)
    result = run_script(str(tmp_path))
    assert result.returncode == par2.OK
    assert (tmp_path / par2.PAR2_NAME).is_file()
    assert (tmp_path / "sub" / par2.PAR2_NAME).is_file()


def test_verify_clean_tree_is_ok(tmp_path: Path) -> None:
    make_tree(tmp_path)
    assert run_script(str(tmp_path)).returncode == par2.OK
    # Second run verifies the existing sets and stays healthy.
    assert run_script(str(tmp_path)).returncode == par2.OK


def test_damaged_file_is_recoverable_warning(tmp_path: Path) -> None:
    # A same-size byte flip inside one data block is always recoverable
    # with the default redundancy, unlike a size change which can make
    # repair impossible.
    payload = bytes(range(256)) * 40
    (tmp_path / "a.bin").write_bytes(payload)
    assert run_script(str(tmp_path)).returncode == par2.OK
    damaged = bytearray(payload)
    damaged[5] ^= 0xFF
    (tmp_path / "a.bin").write_bytes(damaged)
    result = run_script(str(tmp_path))
    assert result.returncode == par2.WARNING
    assert "WARNING! Recoverable error" in result.stdout


def test_missing_file_without_recovery_is_critical(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    assert run_script(str(tmp_path)).returncode == par2.OK
    # Remove the recovery blocks and the file itself: repair impossible.
    for vol in tmp_path.glob(".dir.vol*.par2"):
        vol.unlink()
    (tmp_path / "a.txt").unlink()
    result = run_script(str(tmp_path))
    assert result.returncode == par2.CRITICAL
    assert "CRITICAL! Unrecoverable error" in result.stdout


def test_unprotected_file_warns(tmp_path: Path) -> None:
    make_tree(tmp_path)
    assert run_script(str(tmp_path)).returncode == par2.OK
    (tmp_path / "extra.txt").write_text("unprotected\n")
    result = run_script(str(tmp_path))
    assert result.returncode == par2.WARNING
    assert "Unprotected files" in result.stdout
    assert "extra.txt" in result.stdout


def test_empty_directory_is_skipped(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = run_script(str(empty))
    assert result.returncode == par2.OK
    assert "Empty directory" in result.stdout


def test_process_directory_returns_ok_for_clean_dir(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    assert par2.process_directory(tmp_path) == par2.OK
    assert par2.process_directory(tmp_path) == par2.OK


def test_process_directory_warns_on_too_many_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(par2, "MAX_FILES", 2)
    for i in range(3):
        (tmp_path / f"f{i}.txt").write_text("x\n")
    assert par2.process_directory(tmp_path) == par2.WARNING


def test_main_returns_critical_without_args() -> None:
    assert par2.main(["par2.py"]) == par2.CRITICAL
