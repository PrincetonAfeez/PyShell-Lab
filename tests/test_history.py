"""Test history."""

from __future__ import annotations

from pathlib import Path

from pyshell_lab import history
from pyshell_lab.state import ShellState


def test_load_and_save_history_round_trip(tmp_path) -> None:
    path = tmp_path / "hist"
    path.write_text("line one\nline two\n", encoding="utf-8")

    state = ShellState()
    history.load_history(state, path=path)
    assert state.history == ["line one", "line two"]

    history.remember(state, "line three")
    history.save_history(state, path=path)
    assert path.read_text(encoding="utf-8") == "line one\nline two\nline three\n"


def test_save_history_keeps_last_1000_lines(tmp_path) -> None:
    path = tmp_path / "hist"
    state = ShellState(history=[f"line-{index}" for index in range(1005)])
    history.save_history(state, path=path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1000
    assert lines[0] == "line-5"
    assert lines[-1] == "line-1004"


def test_load_history_skips_blank_lines(tmp_path) -> None:
    path = tmp_path / "hist"
    path.write_text("keep\n\nalso\n", encoding="utf-8")
    state = ShellState()
    history.load_history(state, path=path)
    assert state.history == ["keep", "also"]


def test_load_history_trims_to_history_limit(tmp_path) -> None:
    path = tmp_path / "hist"
    path.write_text("\n".join(f"line-{index}" for index in range(1005)) + "\n", encoding="utf-8")
    state = ShellState()
    history.load_history(state, path=path)
    assert len(state.history) == history.HISTORY_LIMIT
    assert state.history[0] == "line-5"
    assert state.history[-1] == "line-1004"


def test_remember_trims_in_memory_history() -> None:
    state = ShellState()
    for index in range(history.HISTORY_LIMIT + 5):
        history.remember(state, f"line-{index}")
    assert len(state.history) == history.HISTORY_LIMIT
    assert state.history[0] == "line-5"


def test_save_history_empty_writes_empty_string(tmp_path) -> None:
    path = tmp_path / "hist"
    history.save_history(ShellState(), path=path)
    assert path.read_text(encoding="utf-8") == ""


def test_save_history_skips_unchanged_write(tmp_path, monkeypatch) -> None:
    path = tmp_path / "hist"
    state = ShellState(history=["line one"])
    writes: list[str] = []
    original = Path.write_text

    def tracking_write(self, data, *args, **kwargs):
        writes.append(data)
        return original(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", tracking_write)
    history.save_history(state, path=path)
    history.save_history(state, path=path)
    assert writes == ["line one\n"]
