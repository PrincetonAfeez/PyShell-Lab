"""Test init."""

from __future__ import annotations

import pyshell_lab


def test_version_is_string() -> None:
    assert isinstance(pyshell_lab.__version__, str)
    assert pyshell_lab.__version__ == "0.1.0"


def test_all_exports() -> None:
    assert pyshell_lab.__all__ == ["__version__"]
