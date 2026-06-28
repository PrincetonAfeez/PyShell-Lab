"""Test configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

POSIX = os.name != "nt" and hasattr(os, "fork")


@pytest.fixture
def posix() -> bool:
    return POSIX
