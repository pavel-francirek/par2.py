"""Make the script under ``bin/`` importable as the ``par2`` module."""

import sys
from pathlib import Path

BIN_DIR: Path = Path(__file__).resolve().parent.parent / "bin"
sys.path.insert(0, str(BIN_DIR))
