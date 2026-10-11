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


def create(root: Path) -> subprocess.CompletedProcess[str]:
    """Run the script with --create on the given root."""
    return run_script("--create", str(root))


def make_tree(root: Path) -> None:
    """Create a small directory tree with files in the root and a subdir."""
    (root / "a.txt").write_text("hello\n")
    subdir = root / "sub"
    subdir.mkdir()
    (subdir / "b.txt").write_text("world\n")


def test_run_par2_captures_stdout() -> None:
    assert par2.run_par2("echo hello").strip() == "hello"


def test_no_arguments_prints_help_and_exits_critical() -> None:
    result = run_script()
    assert result.returncode == par2.CRITICAL
    assert "usage" in result.stdout.lower()
    assert "--create" in result.stdout
    assert "--silent" in result.stdout


def test_nonexistent_directory_is_critical(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    result = run_script(str(missing))
    assert result.returncode == par2.CRITICAL
    assert "Not a directory" in result.stdout


def test_file_instead_of_directory_is_critical(tmp_path: Path) -> None:
    a_file = tmp_path / "a.txt"
    a_file.write_text("hello\n")
    result = run_script(str(a_file))
    assert result.returncode == par2.CRITICAL
    assert "Not a directory" in result.stdout


def test_silent_nonexistent_directory_is_quiet(tmp_path: Path) -> None:
    result = run_script("--silent", str(tmp_path / "nope"))
    assert result.returncode == par2.CRITICAL
    assert result.stdout == ""


def test_help_prints_usage_and_exits_ok() -> None:
    result = run_script("--help")
    assert result.returncode == par2.OK
    assert "usage" in result.stdout.lower()
    assert "--create" in result.stdout
    assert "--silent" in result.stdout


def test_creates_par2_sets(tmp_path: Path) -> None:
    make_tree(tmp_path)
    result = create(tmp_path)
    assert result.returncode == par2.OK
    assert (tmp_path / par2.PAR2_NAME).is_file()
    assert (tmp_path / "sub" / par2.PAR2_NAME).is_file()


def test_without_create_missing_set_is_skipped(tmp_path: Path) -> None:
    make_tree(tmp_path)
    result = run_script(str(tmp_path))
    assert result.returncode == par2.OK
    assert not (tmp_path / par2.PAR2_NAME).exists()
    assert "skipping" in result.stdout


def test_verify_clean_tree_is_ok(tmp_path: Path) -> None:
    make_tree(tmp_path)
    assert create(tmp_path).returncode == par2.OK
    # Verification-only run of the existing sets stays healthy.
    assert run_script(str(tmp_path)).returncode == par2.OK


def test_damaged_file_is_recoverable_warning(tmp_path: Path) -> None:
    # A same-size byte flip inside one data block is always recoverable
    # with the default redundancy, unlike a size change which can make
    # repair impossible.
    payload = bytes(range(256)) * 40
    (tmp_path / "a.bin").write_bytes(payload)
    assert create(tmp_path).returncode == par2.OK
    damaged = bytearray(payload)
    damaged[5] ^= 0xFF
    (tmp_path / "a.bin").write_bytes(damaged)
    result = run_script(str(tmp_path))
    assert result.returncode == par2.WARNING
    assert "WARNING! Recoverable error" in result.stdout


def test_missing_file_without_recovery_is_critical(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    assert create(tmp_path).returncode == par2.OK
    # Remove the recovery blocks and the file itself: repair impossible.
    for vol in tmp_path.glob(".dir.vol*.par2"):
        vol.unlink()
    (tmp_path / "a.txt").unlink()
    result = run_script(str(tmp_path))
    assert result.returncode == par2.CRITICAL
    assert "CRITICAL! Unrecoverable error" in result.stdout


def test_unprotected_file_warns(tmp_path: Path) -> None:
    make_tree(tmp_path)
    assert create(tmp_path).returncode == par2.OK
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


def test_silent_produces_no_output(tmp_path: Path) -> None:
    make_tree(tmp_path)
    assert create(tmp_path).returncode == par2.OK
    (tmp_path / "extra.txt").write_text("unprotected\n")
    result = run_script("--silent", str(tmp_path))
    assert result.returncode == par2.WARNING
    assert result.stdout == ""
    assert result.stderr == ""


def test_silent_with_create_produces_no_output(tmp_path: Path) -> None:
    make_tree(tmp_path)
    result = run_script("--silent", "--create", str(tmp_path))
    assert result.returncode == par2.OK
    assert result.stdout == ""
    assert (tmp_path / par2.PAR2_NAME).is_file()


def test_process_directory_returns_ok_for_clean_dir(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    assert par2.process_directory(tmp_path, create=True) == par2.OK
    assert par2.process_directory(tmp_path) == par2.OK


def test_process_directory_skips_without_create(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    assert par2.process_directory(tmp_path) == par2.OK
    assert not (tmp_path / par2.PAR2_NAME).exists()
    assert "skipping" in capsys.readouterr().out


def test_process_directory_emit_callback(tmp_path: Path) -> None:
    messages: list[str] = []
    (tmp_path / "a.txt").write_text("hello\n")
    status = par2.process_directory(tmp_path, create=True, emit=messages.append)
    assert status == par2.OK
    assert messages  # creation reports progress when not silent

    messages.clear()
    (tmp_path / "extra.txt").write_text("unprotected\n")
    status = par2.process_directory(tmp_path, emit=messages.append)
    assert status == par2.WARNING
    assert messages


def test_process_directory_warns_on_too_many_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(par2, "MAX_FILES", 2)
    for i in range(3):
        (tmp_path / f"f{i}.txt").write_text("x\n")
    assert par2.process_directory(tmp_path) == par2.WARNING


def test_main_returns_critical_without_args(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert par2.main(["par2.py"]) == par2.CRITICAL
    assert "usage" in capsys.readouterr().out.lower()
