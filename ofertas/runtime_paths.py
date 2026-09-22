"""Caminhos mutáveis do projeto em desenvolvimento e no aplicativo desktop."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    user_root: Path
    config_dir: Path
    data_dir: Path
    logs_dir: Path

    @classmethod
    def for_environment(
        cls,
        project_root: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "RuntimePaths":
        bundled_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        root = Path(project_root or bundled_root)
        env = environ if environ is not None else os.environ
        desktop_home = env.get("BOT_OFERTAS_HOME", "").strip()
        if desktop_home:
            user_root = Path(desktop_home)
            return cls(root, user_root, user_root / "config", user_root / "data", user_root / "logs")
        return cls(root, root, root, root / "data", root / "logs")

    def ensure(self) -> None:
        for path in (self.config_dir, self.data_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)


PATHS = RuntimePaths.for_environment()
PATHS.ensure()
