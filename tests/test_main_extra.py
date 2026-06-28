"""Test main extra."""

from __future__ import annotations

import pytest

from pyshell_lab.main import main


def test_main_help(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    assert "Educational POSIX shell" in capsys.readouterr().out


def test_main_default_interactive(monkeypatch) -> None:
    called: dict[str, bool] = {}

    class FakeShell:
        def run_interactive(self, *, load_rc: bool = True) -> int:
            called["interactive"] = True
            called["load_rc"] = load_rc
            return 0

        def run_script(self, *_args, **_kwargs) -> int:
            raise AssertionError("script should not run")

    monkeypatch.setattr("pyshell_lab.main.Shell", FakeShell)
    assert main([]) == 0
    assert called["interactive"] is True
    assert called["load_rc"] is True


def test_main_no_rc_flag(monkeypatch) -> None:
    class FakeShell:
        def run_interactive(self, *, load_rc: bool = True) -> int:
            assert load_rc is False
            return 0

        def run_script(self, *_args, **_kwargs) -> int:
            raise AssertionError("unexpected script")

    monkeypatch.setattr("pyshell_lab.main.Shell", FakeShell)
    assert main(["--no-rc"]) == 0
