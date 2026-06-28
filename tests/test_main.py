"""Test main."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pyshell_lab import __version__
from pyshell_lab.main import main
from pyshell_lab.repl import Shell

POSIX = os.name != "nt" and hasattr(os, "fork")


def test_main_version(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert f"pyshell {__version__}" in capsys.readouterr().out


def test_main_interactive_no_rc(monkeypatch) -> None:
    called: dict[str, bool] = {}

    class FakeShell:
        def run_interactive(self, *, load_rc: bool = True) -> int:
            called["load_rc"] = load_rc
            return 0

        def run_script(self, *_args, **_kwargs) -> int:
            raise AssertionError("script mode should not run")

    monkeypatch.setattr("pyshell_lab.main.Shell", FakeShell)
    assert main(["--no-rc"]) == 0
    assert called["load_rc"] is False


def test_main_runs_script(monkeypatch, tmp_path) -> None:
    script = tmp_path / "demo.psh"
    script.write_text("echo hi\n", encoding="utf-8")
    called: dict[str, object] = {}

    class FakeShell:
        def run_interactive(self, **_kwargs) -> int:
            raise AssertionError("interactive should not run")

        def run_script(self, path, *, load_rc: bool = True) -> int:
            called["path"] = path
            called["load_rc"] = load_rc
            return 0

    monkeypatch.setattr("pyshell_lab.main.Shell", FakeShell)
    assert main([str(script)]) == 0
    assert called["path"] == script
    assert called["load_rc"] is True


@pytest.mark.skipif(not POSIX, reason="demo script uses pipelines and background jobs")
def test_demo_script_runs(capsys) -> None:
    demo = Path(__file__).resolve().parents[1] / "examples" / "demo.psh"
    assert demo.is_file()
    assert Shell().run_script(demo, load_rc=False) == 0
    out = capsys.readouterr().out
    assert "PyShell Lab demo" in out
    assert "hello Ada" in out
    assert "recovered" in out
    assert "done" in out
