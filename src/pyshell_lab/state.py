"""Explicit mutable shell state."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .jobs import JobTable


@dataclass
class ShellState:
    cwd: str = field(default_factory=os.getcwd)
    previous_cwd: str | None = None
    variables: dict[str, str] = field(default_factory=dict)
    exported_env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    last_status: int = 0
    jobs: JobTable = field(default_factory=JobTable)
    history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.variables.setdefault("PWD", self.cwd)
        self.variables.setdefault("OLDPWD", self.previous_cwd or "")
        self.exported_env.setdefault("PWD", self.cwd)

    def set_cwd(self, path: str) -> None:
        old = self.cwd
        os.chdir(path)
        self.previous_cwd = old
        self.cwd = os.getcwd()
        self.variables["PWD"] = self.cwd
        self.variables["OLDPWD"] = old
        self.exported_env["PWD"] = self.cwd
        self.exported_env["OLDPWD"] = old

    def environment(self) -> dict[str, str]:
        env = dict(self.exported_env)
        env["PWD"] = self.cwd
        return env

    def home(self) -> str | None:
        # Resolve HOME with shell-variable precedence, matching variable lookup,
        # then the exported environment. Returns None when HOME is set nowhere.
        if "HOME" in self.variables:
            return self.variables["HOME"]
        return self.exported_env.get("HOME")
